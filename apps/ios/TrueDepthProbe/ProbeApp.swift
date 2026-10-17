import SwiftUI
import AVFoundation
import Network
import CryptoKit
import Darwin
import CoreImage

@main
struct ProbeApp: App {
    @StateObject private var probe = Probe()
    var body: some Scene {
        WindowGroup {
            VStack(alignment: .leading, spacing: 22) {
                Text("TrueDepth · RGB-D v3").font(.title.bold())
                Text(probe.status)
                Text("IP Wi-Fi: \(Probe.wifiAddress())\nPuerto: 8765")
                Text("Código: \(probe.token)").font(.system(.title2, design: .monospaced)).textSelection(.enabled)
                Text("Mantené esta app abierta. La cámara frontal apunta al objeto. En Windows ejecutá Capturar-secuencia.ps1 con esta IP y código.")
                ShareLink("Compartir registro de transporte", item: probe.transport.logURL)
                Button("Activar TrueDepth") { probe.start() }.buttonStyle(.borderedProminent).disabled(probe.started)
                Text("RGB y profundidad sincronizados. Sin tracking ni reconstrucción.").font(.footnote)
            }.padding(26)
        }
    }
}

final class Probe: NSObject, ObservableObject, AVCaptureDataOutputSynchronizerDelegate {
    @Published var status = "Sensor todavía inactivo"
    @Published var started = false
    let token = UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(12).lowercased()
    private let queue = DispatchQueue(label: "truedepth.capture")
    private let session = AVCaptureSession()
    let transport = ProbeTransport()
    private let latestLock = NSLock()
    private struct Pair {
        let depth: AVDepthData
        let rgb: CVPixelBuffer
        let depthTime: CMTime
        let rgbTime: CMTime
        let arrival: Date
        let id: Int
        let settings: [String: Any]
        let rejected: Int
    }
    private var latest: Pair?
    private var sequence = 0
    private var formats: [[String: Any]] = []
    private let depthOutput = AVCaptureDepthDataOutput()
    private let videoOutput = AVCaptureVideoDataOutput()
    private var synchronizer: AVCaptureDataOutputSynchronizer?
    private var captureDevice: AVCaptureDevice?
    private var rejectedPairs = 0
    private let imageContext = CIContext(options: [.cacheIntermediates: false])

    private func report(_ text: String) { DispatchQueue.main.async { self.status = text } }
    func start() {
        started = true
        UIApplication.shared.isIdleTimerDisabled = true
        AVCaptureDevice.requestAccess(for: .video) { granted in
            guard granted else { self.report("Permiso de cámara denegado. Habilitalo en Ajustes."); return }
            self.queue.async {
                do {
                    try self.configure(); self.session.startRunning()
                    try self.transport.start(token: self.token, packet: { try self.packet(includeRGB: $0) }, report: self.report)
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
        captureDevice = device
        let output = depthOutput
        output.isFilteringEnabled = false
        output.alwaysDiscardsLateDepthData = true
        guard session.canAddOutput(output) else { throw failure("No se puede agregar salida depth") }
        session.addOutput(output)
        videoOutput.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        videoOutput.alwaysDiscardsLateVideoFrames = true
        guard session.canAddOutput(videoOutput) else { throw failure("No se puede agregar salida RGB") }
        session.addOutput(videoOutput)
        for connection in [output.connection(with: .depthData), videoOutput.connection(with: .video)].compactMap({ $0 }) {
            if connection.isVideoMirroringSupported {
                connection.automaticallyAdjustsVideoMirroring = false
                connection.isVideoMirrored = false
            }
            // Explicitly keep native buffers; record the effective values per pair.
            if connection.isVideoRotationAngleSupported(0) { connection.videoRotationAngle = 0 }
            if connection.isVideoStabilizationSupported { connection.preferredVideoStabilizationMode = .off }
        }
        let sync = AVCaptureDataOutputSynchronizer(dataOutputs: [videoOutput, depthOutput])
        synchronizer = sync
        sync.setDelegate(self, queue: queue)
    }
    private func failure(_ message: String) -> NSError {
        NSError(domain: "TrueDepth", code: 3, userInfo: [NSLocalizedDescriptionKey: message])
    }
    private func stamp(_ time: CMTime) -> [String: Any] {
        ["value": time.value, "timescale": time.timescale, "seconds": CMTimeGetSeconds(time), "clock": "capture-session"]
    }
    private func connectionInfo(_ connection: AVCaptureConnection?) -> [String: Any] {
        guard let c = connection else { return ["available": false] }
        return ["available": true, "rotation_degrees": c.videoRotationAngle,
                "mirrored": c.isVideoMirrored, "stabilization_raw": c.activeVideoStabilizationMode.rawValue]
    }
    func dataOutputSynchronizer(_ synchronizer: AVCaptureDataOutputSynchronizer,
                                didOutput collection: AVCaptureSynchronizedDataCollection) {
        sequence += 1
        guard let d = collection.synchronizedData(for: depthOutput) as? AVCaptureSynchronizedDepthData,
              let v = collection.synchronizedData(for: videoOutput) as? AVCaptureSynchronizedSampleBufferData,
              !d.depthDataWasDropped, !v.sampleBufferWasDropped,
              let rgb = CMSampleBufferGetImageBuffer(v.sampleBuffer) else {
            rejectedPairs += 1
            return
        }
        let rgbTime = CMSampleBufferGetPresentationTimeStamp(v.sampleBuffer)
        let delta = CMTimeGetSeconds(CMTimeSubtract(rgbTime, d.timestamp))
        guard delta.isFinite, abs(delta) <= 0.001, let device = captureDevice else {
            rejectedPairs += 1
            return
        }
        let videoSize = CMVideoFormatDescriptionGetDimensions(device.activeFormat.formatDescription)
        var settings: [String: Any] = [
            "video_format_width": videoSize.width, "video_format_height": videoSize.height,
            "video_subtype": CMFormatDescriptionGetMediaSubType(device.activeFormat.formatDescription),
            "zoom_factor": device.videoZoomFactor, "lens_position": device.lensPosition,
            "depth_connection": connectionInfo(depthOutput.connection(with: .depthData)),
            "rgb_connection": connectionInfo(videoOutput.connection(with: .video))]
        if let format = device.activeDepthDataFormat {
            let size = CMVideoFormatDescriptionGetDimensions(format.formatDescription)
            settings["depth_format_width"] = size.width
            settings["depth_format_height"] = size.height
            settings["depth_subtype"] = CMFormatDescriptionGetMediaSubType(format.formatDescription)
        }
        latestLock.lock()
        let first = latest == nil
        latest = Pair(depth: d.depthData, rgb: rgb, depthTime: d.timestamp, rgbTime: rgbTime,
                      arrival: Date(), id: sequence, settings: settings, rejected: rejectedPairs)
        latestLock.unlock()
        if first { report("RGB-D sincronizado activo. Esperando solicitud de Windows.") }
    }
    private func packet(includeRGB: Bool) throws -> Data {
        latestLock.lock()
        let snapshot = latest
        latestLock.unlock()
        guard let pair = snapshot, Date().timeIntervalSince(pair.arrival) < 2 else {
            throw failure("Sin par RGB-D reciente. Mantené la app abierta y reintentá.")
        }
        let depth = pair.depth.converting(toDepthDataType: kCVPixelFormatType_DepthFloat32)
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
        var header: [String: Any] = [
            "protocol": "td-frame/1", "source": "iphone-truedepth", "frame_id": pair.id,
            "width": w, "height": h, "encoding": "float32-le", "units": "meters",
            "payload_bytes": raw.count, "sha256": SHA256.hash(data: raw).map { String(format: "%02x", $0) }.joined(),
            "timestamp": stamp(pair.depthTime),
            "ios_version": ProcessInfo.processInfo.operatingSystemVersionString,
            "filtered": depth.isDepthDataFiltered, "accuracy_raw": depth.depthDataAccuracy.rawValue,
            "quality_raw": depth.depthDataQuality.rawValue, "orientation": "native-depth-buffer-unmirrored",
            "calibration": calibration, "available_formats": formats, "capture_settings": pair.settings
        ]
        var color = Data()
        if includeRGB {
            guard let png = imageContext.pngRepresentation(of: CIImage(cvPixelBuffer: pair.rgb),
                format: .RGBA8, colorSpace: CGColorSpace(name: CGColorSpace.sRGB)!, options: [:]),
                png.count <= 32 * 1024 * 1024 else { throw failure("No se pudo codificar RGB PNG") }
            color = png
            header["rgb"] = ["protocol": "td-rgb/1", "encoding": "png", "frame_id": pair.id,
                "width": CVPixelBufferGetWidth(pair.rgb), "height": CVPixelBufferGetHeight(pair.rgb),
                "payload_bytes": color.count, "sha256": SHA256.hash(data: color).map { String(format: "%02x", $0) }.joined(),
                "timestamp": stamp(pair.rgbTime), "color_space": "sRGB", "resized": false]
            header["synchronization"] = ["method": "AVCaptureDataOutputSynchronizer",
                "depth_dropped": false, "rgb_dropped": false, "rejected_pairs_total": pair.rejected,
                "max_timestamp_delta_ms": 1,
                "timestamp_delta_ms": CMTimeGetSeconds(CMTimeSubtract(pair.rgbTime, pair.depthTime)) * 1000]
        }
        let json = try JSONSerialization.data(withJSONObject: header, options: [.sortedKeys])
        var length = UInt32(json.count).bigEndian
        var packet = withUnsafeBytes(of: &length) { Data($0) }
        packet.append(json); packet.append(raw); packet.append(color)
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
