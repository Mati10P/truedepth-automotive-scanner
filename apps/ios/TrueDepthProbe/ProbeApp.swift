import SwiftUI
import AVFoundation
import Network
import CryptoKit
import Darwin
import CoreImage

@main
struct ProbeApp: App {
    @StateObject private var probe = Probe()
    @State private var manualPosition = "0.56078434"
    var body: some Scene {
        WindowGroup {
            ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                Text("TrueDepth · RGB-D v9 · 4:3").font(.title.bold())
                Button("Activar TrueDepth") { probe.start() }.buttonStyle(.borderedProminent).disabled(probe.started)
                CameraPreview(session: probe.sensorReady ? probe.session : nil, device: probe.previewDevice)
                    .aspectRatio(3.0 / 4.0, contentMode: .fit)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .overlay {
                        if !probe.sensorReady {
                            Text("Activá TrueDepth para ver la cámara").foregroundStyle(.white)
                        }
                    }
                Text(probe.focusStatus).font(.callout)
                HStack {
                    Button("Enfocar centro") { probe.refocus() }
                    Button("Bloquear foco actual") { probe.lockFocus() }
                }.disabled(!probe.sensorReady)
                Text("Centrá la cara con la cuadrícula, enfocá y revisá que los bordes se vean nítidos antes de bloquear.").font(.footnote)
                Text(probe.status)
                Text("IP Wi-Fi: \(Probe.wifiAddress())\nPuerto: 8765")
                Text("Código: \(probe.token)").font(.system(.title2, design: .monospaced)).textSelection(.enabled)
                Text("Mantené esta app abierta. La cámara frontal apunta al objeto. En Windows ejecutá Capturar-RGBD.ps1 con esta IP y código.")
                ShareLink("Compartir registro de transporte", item: probe.transport.logURL)
                Text("Para calibrar: apuntá al tablero, enfocá, esperá y bloqueá. Conservá ese bloqueo para medir.").font(.footnote)
                Text("RGB y profundidad sincronizados. Sin tracking ni reconstrucción.").font(.footnote)
            }.padding(26).onReceive(NotificationCenter.default.publisher(for: UIApplication.willResignActiveNotification)) { _ in
                probe.invalidateFocus()
            }.onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
                probe.restoreManualFocus()
            }
            }
        }
    }
}

final class Probe: NSObject, ObservableObject, AVCaptureDataOutputSynchronizerDelegate {
    @Published var status = "Sensor todavía inactivo"
    @Published var started = false
    @Published var sensorReady = false
    @Published var focusStatus = "Foco: sensor inactivo"
    @Published var previewDevice: AVCaptureDevice?
    private var focusCompletionReceived = false
    private var focusState = "unlocked"
    private var focusGeneration = 0
    private var focusProfileID = UUID().uuidString
    private var lockBoundary: CMTime?
    private var lockedPosition: Float?
    private var requestedPosition: Float?
    let token = UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(12).lowercased()
    private let queue = DispatchQueue(label: "truedepth.capture")
    let session = AVCaptureSession()
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

    // Capture-queue only. Completion and observable focus state may settle on
    // different turns. Wait for both instead of failing inside the callback.
    private func confirmPendingFocus() {
        guard focusState == "locking", focusCompletionReceived,
              let device = captureDevice, device.focusMode == .locked,
              !device.isAdjustingFocus,
              requestedPosition == nil || abs(device.lensPosition - requestedPosition!) < 0.0001,
              let clock = session.synchronizationClock else { return }
        let boundary = CMClockGetTime(clock)
        guard boundary.isValid, !boundary.isIndefinite, CMTimeGetSeconds(boundary).isFinite else { return }
        lockBoundary = boundary
        lockedPosition = device.lensPosition
        focusState = "locked"
        clearPair()
        focusReport("Foco bloqueado; esperando un par nuevo.")
    }

    private func report(_ text: String) { DispatchQueue.main.async { self.status = text } }
    private func focusReport(_ text: String) { DispatchQueue.main.async { self.focusStatus = text } }
    private func clearPair() {
        latestLock.lock(); latest = nil; latestLock.unlock()
    }
    func invalidateFocus() {
        queue.async {
            self.focusGeneration += 1
            self.focusState = "invalidated"
            self.lockBoundary = nil
            self.clearPair()
            self.focusReport("Foco invalidado al salir de la app. Volvé a enfocar y bloquear.")
        }
    }
    func refocus() {
        queue.async {
            guard let device = self.captureDevice else { return }
            guard device.isFocusModeSupported(.autoFocus) else {
                self.focusReport("Este formato no admite autofocus puntual."); return
            }
            do {
                try device.lockForConfiguration()
                defer { device.unlockForConfiguration() }
                self.focusGeneration += 1
                self.focusProfileID = UUID().uuidString
                UserDefaults.standard.removeObject(forKey: "manualLensPosition")
                self.requestedPosition = nil
                self.focusState = "unlocked"
                self.lockBoundary = nil; self.lockedPosition = nil
                self.clearPair()
                if device.isFocusPointOfInterestSupported { device.focusPointOfInterest = CGPoint(x: 0.5, y: 0.5) }
                device.focusMode = .autoFocus
                self.focusReport("Enfocando el centro; esperá antes de bloquear.")
            } catch { self.focusReport("No se pudo enfocar: \(error.localizedDescription)") }
        }
    }
    func lockFocus(position: Float? = nil) {
        queue.async {
            guard let device = self.captureDevice else { return }
            if let position = position {
                guard position.isFinite, (0...1).contains(position), device.isLockingFocusWithCustomLensPositionSupported else {
                    self.focusReport("Posici�n manual inv�lida o no compatible."); return
                }
            }
            guard device.isFocusModeSupported(.locked) else {
                self.focusState = "unsupported"; self.clearPair()
                self.focusReport("Bloqueo de foco no disponible en este formato."); return
            }
            guard !device.isAdjustingFocus else {
                self.focusReport("El foco sigue ajustándose; esperá y volvé a bloquear."); return
            }
            do {
                try device.lockForConfiguration()
                defer { device.unlockForConfiguration() }
                self.focusGeneration += 1
                let generation = self.focusGeneration
                self.focusProfileID = UUID().uuidString
                self.requestedPosition = position
                if let position = position { UserDefaults.standard.set(position, forKey: "manualLensPosition") }
                self.focusState = "locking"; self.lockBoundary = nil
                self.focusCompletionReceived = false
                self.clearPair()
                self.focusReport("Esperando confirmación del bloqueo…")
                // Current position is allowed even without arbitrary-position support.
                device.setFocusModeLocked(lensPosition: position ?? AVCaptureDevice.currentLensPosition) { _ in
                    self.queue.async {
                        guard generation == self.focusGeneration else { return }
                        self.focusCompletionReceived = true
                        self.confirmPendingFocus()
                    }
                }
                self.queue.asyncAfter(deadline: .now() + 5) {
                    guard generation == self.focusGeneration, self.focusState == "locking" else { return }
                    self.focusGeneration += 1; self.focusState = "failed"; self.clearPair()
                    let reason: String
                    if !self.focusCompletionReceived { reason = "La cámara no confirmó la solicitud de bloqueo." }
                    else if device.focusMode != .locked { reason = "La cámara no mantuvo el modo de foco bloqueado." }
                    else if device.isAdjustingFocus { reason = "La lente sigue ajustándose." }
                    else { reason = "No hay reloj de sincronización válido para verificar las capturas." }
                    self.focusReport(reason + " Volvé a intentar.")
                }
            } catch { self.focusState = "failed"; self.clearPair(); self.focusReport("Error de bloqueo: \(error.localizedDescription)") }
        }
    }
    func restoreManualFocus() {
        if let value = UserDefaults.standard.object(forKey: "manualLensPosition") as? NSNumber {
            lockFocus(position: value.floatValue)
        }
    }

    // Called only from transport preparation queue. All camera state stays on capture queue.
    func focusControl(_ command: String) -> [String: Any] {
        if command != "status" {
            guard command.hasPrefix("set:"), let value = Float(command.dropFirst(4)),
                  value.isFinite, (0...1).contains(value) else {
                return ["ok": false, "error": "Use status or set:<finite position 0..1>"]
            }
            let supported = queue.sync { captureDevice?.isLockingFocusWithCustomLensPositionSupported == true }
            guard supported else { return ["ok": false, "error": "Custom lens position unavailable"] }
            lockFocus(position: value)
        }
        return queue.sync {
            guard let device = captureDevice else { return ["ok": false, "error": "Camera inactive"] }
            return ["ok": true, "state": focusState, "profile_id": focusProfileID,
                    "lens_position": device.lensPosition, "is_adjusting": device.isAdjustingFocus,
                    "lock_confirmed": focusState == "locked" && device.focusMode == .locked && !device.isAdjustingFocus,
                    "requested_position": requestedPosition.map { $0 as Any } ?? NSNull()]
        }
    }

    func start() {
        started = true
        UIApplication.shared.isIdleTimerDisabled = true
        AVCaptureDevice.requestAccess(for: .video) { granted in
            guard granted else { self.report("Permiso de cámara denegado. Habilitalo en Ajustes."); return }
            self.queue.async {
                do {
                    try self.configure(); self.session.startRunning()
                    self.restoreManualFocus()
                    DispatchQueue.main.async { self.previewDevice = self.captureDevice; self.sensorReady = true }
                    try self.transport.start(token: self.token, control: self.focusControl, packet: { try self.packet(includeRGB: $0) }, report: self.report)
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
        // Exact requested RGB format; never silently fall back or upscale.
        let rgbFormats = candidates.filter {
            let size = CMVideoFormatDescriptionGetDimensions($0.formatDescription)
            return size.width == 1440 && size.height == 1080 &&
                $0.supportedDepthDataFormats.contains { format in
                    let depthSize = CMVideoFormatDescriptionGetDimensions(format.formatDescription)
                    return depthSize.width == 640 && depthSize.height == 480
                }
        }
        guard let video = rgbFormats.first,
              let depth = video.supportedDepthDataFormats.max(by: { area($0) < area($1) }) else {
            throw NSError(domain: "TrueDepth", code: 2, userInfo: [NSLocalizedDescriptionKey: "No hay formato RGB 1440 × 1080 compatible con profundidad"])
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
        videoOutput.automaticallyConfiguresOutputBufferDimensions = false
        videoOutput.deliversPreviewSizedOutputBuffers = false
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
        let depthBuffer = d.depthData.depthDataMap
        guard CVPixelBufferGetWidth(rgb) == 1440, CVPixelBufferGetHeight(rgb) == 1080,
              CVPixelBufferGetWidth(depthBuffer) == 640, CVPixelBufferGetHeight(depthBuffer) == 480 else {
            clearPair(); rejectedPairs += 1
            if sequence % 30 == 0 { report("La cámara no entregó RGB 1440 × 1080 y depth 640 × 480; captura rechazada.") }
            return
        }
        confirmPendingFocus()
        let adjusting = device.isAdjustingFocus
        let position = device.lensPosition
        if focusState == "locked" {
            guard device.focusMode == .locked, !adjusting,
                  let expected = lockedPosition, abs(position - expected) < 0.0001 else {
                focusState = "invalidated"; clearPair()
                focusReport("El foco cambió: bloqueo invalidado. Volvé a bloquear.")
                rejectedPairs += 1; return
            }
            guard let boundary = lockBoundary,
                  CMTimeCompare(rgbTime, boundary) > 0, CMTimeCompare(d.timestamp, boundary) > 0 else {
                rejectedPairs += 1; return
            }
        } else if focusState != "unlocked" && focusState != "unsupported" {
            clearPair(); rejectedPairs += 1; return
        }
        if sequence % 15 == 0 {
            focusReport("\(focusState == "locked" ? "Foco bloqueado" : "Foco sin bloqueo confirmado") · \(adjusting ? "ajustando" : "estable") · lente \(String(format: "%.6f", position))")
        }
        let videoSize = CMVideoFormatDescriptionGetDimensions(device.activeFormat.formatDescription)
        var settings: [String: Any] = [
            "video_format_width": videoSize.width, "video_format_height": videoSize.height,
            "video_subtype": CMFormatDescriptionGetMediaSubType(device.activeFormat.formatDescription),
            "zoom_factor": device.videoZoomFactor, "lens_position": device.lensPosition,
            "app_version": "0.9.0",
            "resolution_policy": "native-rgb-1440x1080-depth-640x480",
            "rgb_buffer_width": CVPixelBufferGetWidth(rgb),
            "rgb_buffer_height": CVPixelBufferGetHeight(rgb),
            "automatically_configures_output_dimensions": videoOutput.automaticallyConfiguresOutputBufferDimensions,
            "preview_sized_output_buffers": videoOutput.deliversPreviewSizedOutputBuffers,
            "focus": ["state": focusState, "profile_id": focusProfileID,
                      "mode_raw": device.focusMode.rawValue, "is_adjusting": adjusting,
                      "lens_position": position, "lock_confirmed": focusState == "locked",
                      "supports_locked": device.isFocusModeSupported(.locked),
                      "supports_auto": device.isFocusModeSupported(.autoFocus),
                      "supports_continuous_auto": device.isFocusModeSupported(.continuousAutoFocus),
                      "supports_custom_position": device.isLockingFocusWithCustomLensPositionSupported,
                      "observation": "device state at synchronized callback; not exposure metadata",
                      "confirmation_method": "completion_and_stable_state_then_synchronization_clock",
                      "sample_clock_boundary": lockBoundary.map { self.stamp($0) } as Any? ?? NSNull()] as [String: Any],
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
        if first {
            let depthBuffer = d.depthData.depthDataMap
            report("RGB 1440 × 1080 · depth \(CVPixelBufferGetWidth(depthBuffer)) × \(CVPixelBufferGetHeight(depthBuffer)). Sincronizados; listo para Windows.")
        }
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
