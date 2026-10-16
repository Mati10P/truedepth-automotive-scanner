import SwiftUI
import AVFoundation
import Network
import CryptoKit
import Darwin

@main
struct ProbeApp: App {
    @StateObject private var probe = Probe()
    var body: some Scene {
        WindowGroup {
            VStack(alignment: .leading, spacing: 22) {
                Text("TrueDepth · transporte v2").font(.title.bold())
                Text(probe.status)
                Text("IP Wi-Fi: \(Probe.wifiAddress())\nPuerto: 8765")
                Text("Código: \(probe.token)").font(.system(.title2, design: .monospaced)).textSelection(.enabled)
                Text("Mantené esta app abierta. La cámara frontal apunta al objeto. En Windows ejecutá Capturar-secuencia.ps1 con esta IP y código.")
                ShareLink("Compartir registro de transporte", item: probe.transport.logURL)
                Button("Activar TrueDepth") { probe.start() }.buttonStyle(.borderedProminent).disabled(probe.started)
                Text("Prueba de profundidad solamente. Sin RGB, tracking ni reconstrucción.").font(.footnote)
            }.padding(26)
        }
    }
}

final class Probe: NSObject, ObservableObject, AVCaptureDepthDataOutputDelegate {
    @Published var status = "Sensor todavía inactivo"
    @Published var started = false
    let token = UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(12).lowercased()
    private let queue = DispatchQueue(label: "truedepth.capture")
    private let session = AVCaptureSession()
    let transport = ProbeTransport()
    private let latestLock = NSLock()
    private var latest: (AVDepthData, CMTime, Date)?
    private var sequence = 0
    private var formats: [[String: Any]] = []

    private func report(_ text: String) { DispatchQueue.main.async { self.status = text } }
    func start() {
        started = true
        UIApplication.shared.isIdleTimerDisabled = true
        AVCaptureDevice.requestAccess(for: .video) { granted in
            guard granted else { self.report("Permiso de cámara denegado. Habilitalo en Ajustes."); return }
            self.queue.async {
                do {
                    try self.configure(); self.session.startRunning()
                    try self.transport.start(token: self.token, packet: { try self.packet() }, report: self.report)
                }
                catch { self.report("Error: \(error.localizedDescription). Cerrá y reabrí la app para reintentar.") }
            }
        }
    }

    private func configure() throws {
        guard let device = AVCaptureDevice.default(.builtInTrueDepthCamera, for: .video, position: .front) else {
            throw NSError(domain: "TrueDepth", code: 1, userInfo: [NSLocalizedDescriptionKey: "No se encontró cámara TrueDepth frontal"])
        }
        let candidates = device.formats.filter { !$0.supportedDepthDataFormats.isEmpty }
        func area(_ format: AVCaptureDevice.Format) -> Int32 {
            let d = CMVideoFormatDescriptionGetDimensions(format.formatDescription)
            return d.width * d.height
        }
        guard let video = candidates.min(by: { area($0) < area($1) }),
              let depth = video.supportedDepthDataFormats.max(by: { area($0) < area($1) }) else {
            throw NSError(domain: "TrueDepth", code: 2, userInfo: [NSLocalizedDescriptionKey: "Sin formato de profundidad"])
        }
        formats = candidates.map { f in
            let d = CMVideoFormatDescriptionGetDimensions(f.formatDescription)
            return ["video_width": d.width, "video_height": d.height,
                    "depth_formats": f.supportedDepthDataFormats.map { df -> [String: Any] in
                        let dd = CMVideoFormatDescriptionGetDimensions(df.formatDescription)
                        return ["width": dd.width, "height": dd.height,
                                "subtype": CMFormatDescriptionGetMediaSubType(df.formatDescription)]
                    }]
        }
        session.beginConfiguration()
        defer { session.commitConfiguration() }
        session.sessionPreset = .inputPriority
        let input = try AVCaptureDeviceInput(device: device)
        guard session.canAddInput(input) else { throw failure("No se puede agregar cámara") }
        session.addInput(input)
        try device.lockForConfiguration()
        device.activeFormat = video
        device.activeDepthDataFormat = depth
        device.unlockForConfiguration()
        let output = AVCaptureDepthDataOutput()
        output.isFilteringEnabled = false
        output.alwaysDiscardsLateDepthData = true
        guard session.canAddOutput(output) else { throw failure("No se puede agregar salida depth") }
        session.addOutput(output)
        output.setDelegate(self, callbackQueue: queue)
        if let connection = output.connection(with: .depthData), connection.isVideoMirroringSupported {
            connection.automaticallyAdjustsVideoMirroring = false
            connection.isVideoMirrored = false
        }
    }
    private func failure(_ message: String) -> NSError {
        NSError(domain: "TrueDepth", code: 3, userInfo: [NSLocalizedDescriptionKey: message])
    }
    func depthDataOutput(_ output: AVCaptureDepthDataOutput, didOutput depthData: AVDepthData,
                         timestamp: CMTime, connection: AVCaptureConnection) {
        latestLock.lock()
        latest = (depthData, timestamp, Date())
        sequence += 1
        let first = sequence == 1
        latestLock.unlock()
        if first { report("TrueDepth activo. Esperando solicitud de Windows.") }
    }
    private func packet() throws -> Data {
        latestLock.lock()
        let snapshot = latest, frameID = sequence
        latestLock.unlock()
        guard let (source, timestamp, arrival) = snapshot, Date().timeIntervalSince(arrival) < 2 else {
            throw failure("Sin frame reciente. Mantené la app abierta y reintentá.")
        }
        let depth = source.converting(toDepthDataType: kCVPixelFormatType_DepthFloat32)
        let buffer = depth.depthDataMap
        guard CVPixelBufferLockBaseAddress(buffer, .readOnly) == kCVReturnSuccess else { throw failure("No se pudo leer depth") }
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        guard let base = CVPixelBufferGetBaseAddress(buffer) else { throw failure("Depth vacío") }
        let w = CVPixelBufferGetWidth(buffer), h = CVPixelBufferGetHeight(buffer)
        var raw = Data(capacity: w * h * 4)
        for y in 0..<h { raw.append(base.advanced(by: y * CVPixelBufferGetBytesPerRow(buffer)).assumingMemoryBound(to: UInt8.self), count: w * 4) }
        var calibration: Any = NSNull()
        if let c = depth.cameraCalibrationData {
            let k = c.intrinsicMatrix, e = c.extrinsicMatrix
            calibration = [
                "intrinsic_matrix_rows": (0..<3).map { r in (0..<3).map { k[$0][r] } },
                "intrinsic_reference_width": c.intrinsicMatrixReferenceDimensions.width,
                "intrinsic_reference_height": c.intrinsicMatrixReferenceDimensions.height,
                "extrinsic_matrix_rows": (0..<3).map { r in (0..<4).map { e[$0][r] } },
                "pixel_size_mm": c.pixelSize,
                "lens_distortion_center": [c.lensDistortionCenter.x, c.lensDistortionCenter.y],
                "lens_distortion_lookup_f32le_b64": c.lensDistortionLookupTable?.base64EncodedString() as Any? ?? NSNull(),
                "inverse_lens_distortion_lookup_f32le_b64": c.inverseLensDistortionLookupTable?.base64EncodedString() as Any? ?? NSNull()
            ] as [String: Any]
        }
        let header: [String: Any] = [
            "protocol": "td-frame/1", "source": "iphone-truedepth", "frame_id": frameID,
            "width": w, "height": h, "encoding": "float32-le", "units": "meters",
            "payload_bytes": raw.count, "sha256": SHA256.hash(data: raw).map { String(format: "%02x", $0) }.joined(),
            "timestamp": ["value": timestamp.value, "timescale": timestamp.timescale, "seconds": CMTimeGetSeconds(timestamp), "clock": "capture-session"],
            "ios_version": ProcessInfo.processInfo.operatingSystemVersionString,
            "filtered": depth.isDepthDataFiltered, "accuracy_raw": depth.depthDataAccuracy.rawValue,
            "quality_raw": depth.depthDataQuality.rawValue, "orientation": "native-depth-buffer-unmirrored",
            "calibration": calibration, "available_formats": formats
        ]
        let json = try JSONSerialization.data(withJSONObject: header, options: [.sortedKeys])
        var length = UInt32(json.count).bigEndian
        var packet = withUnsafeBytes(of: &length) { Data($0) }
        packet.append(json); packet.append(raw)
        return packet
    }
    static func wifiAddress() -> String {
        var addresses: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&addresses) == 0 else { return "ver Ajustes > Wi-Fi" }
        defer { freeifaddrs(addresses) }
        var cursor = addresses
        while let item = cursor {
            defer { cursor = item.pointee.ifa_next }
            guard String(cString: item.pointee.ifa_name) == "en0", let address = item.pointee.ifa_addr,
                  address.pointee.sa_family == UInt8(AF_INET) else { continue }
            var host = [CChar](repeating: 0, count: Int(NI_MAXHOST))
            if getnameinfo(address, socklen_t(address.pointee.sa_len), &host, socklen_t(host.count), nil, 0, NI_NUMERICHOST) == 0 {
                return String(cString: host)
            }
        }
        return "ver Ajustes > Wi-Fi"
    }
}
