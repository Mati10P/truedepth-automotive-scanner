import SwiftUI
import AVFoundation

/// Native camera rendering; no UIImage conversion or SwiftUI updates per frame.
struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession?
    let device: AVCaptureDevice?

    func makeUIView(context: Context) -> CameraPreviewView { CameraPreviewView() }
    func updateUIView(_ view: CameraPreviewView, context: Context) {
        view.connect(session: session, device: device)
    }
}

final class CameraPreviewView: UIView {
    override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
    private var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    private let grid = CAShapeLayer()
    private var device: AVCaptureDevice?
    private var rotation: AVCaptureDevice.RotationCoordinator?
    private var observation: NSKeyValueObservation?

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .black
        previewLayer.videoGravity = .resizeAspect
        grid.strokeColor = UIColor.white.withAlphaComponent(0.65).cgColor
        grid.fillColor = UIColor.clear.cgColor
        grid.lineWidth = 1
        grid.shadowColor = UIColor.black.cgColor
        grid.shadowOpacity = 0.6
        grid.shadowRadius = 1
        layer.addSublayer(grid)
        isAccessibilityElement = true
        accessibilityLabel = "Vista de cámara con cuadrícula de tercios"
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    func connect(session: AVCaptureSession?, device: AVCaptureDevice?) {
        if previewLayer.session !== session { previewLayer.session = session }
        if self.device !== device {
            self.device = device
            startRotation()
        }
        applyRotation()
    }

    override func didMoveToWindow() {
        super.didMoveToWindow()
        // The coordinator needs the layer in a view hierarchy to compute angles.
        startRotation()
    }

    private func startRotation() {
        observation = nil
        rotation = nil
        guard window != nil, let device else { return }
        let coordinator = AVCaptureDevice.RotationCoordinator(device: device, previewLayer: previewLayer)
        rotation = coordinator
        observation = coordinator.observe(\.videoRotationAngleForHorizonLevelPreview, options: [.initial, .new]) { [weak self] _, _ in
            // Apple delivers rotation-coordinator observations on the main queue.
            self?.applyRotation()
        }
    }

    private func applyRotation() {
        guard let connection = previewLayer.connection, let rotation else { return }
        let angle = rotation.videoRotationAngleForHorizonLevelPreview
        if connection.isVideoRotationAngleSupported(angle) { connection.videoRotationAngle = angle }
        if connection.isVideoMirroringSupported {
            connection.automaticallyAdjustsVideoMirroring = false
            connection.isVideoMirrored = true
        }
        setNeedsLayout()
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        // Grid follows actual image bounds, excluding resizeAspect letterboxing.
        let rect = previewLayer.layerRectConverted(fromMetadataOutputRect: CGRect(x: 0, y: 0, width: 1, height: 1))
        let path = UIBezierPath()
        if device != nil, !rect.isEmpty, !rect.isInfinite, !rect.isNull {
            for division in 1...2 {
                let fraction = CGFloat(division) / 3
                let x = rect.minX + rect.width * fraction
                let y = rect.minY + rect.height * fraction
                path.move(to: CGPoint(x: x, y: rect.minY))
                path.addLine(to: CGPoint(x: x, y: rect.maxY))
                path.move(to: CGPoint(x: rect.minX, y: y))
                path.addLine(to: CGPoint(x: rect.maxX, y: y))
            }
        }
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        grid.frame = bounds
        grid.path = path.cgPath
        CATransaction.commit()
    }
}
