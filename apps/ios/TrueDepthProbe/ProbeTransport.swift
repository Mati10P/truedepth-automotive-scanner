import Foundation
import Network
import OSLog

/// All connection state belongs to networkQueue; capture and packet work never run there.
final class ProbeTransport {
    private let networkQueue = DispatchQueue(label: "truedepth.network")
    private let preparationQueue = DispatchQueue(label: "truedepth.prepare")
    private let logQueue = DispatchQueue(label: "truedepth.log")
    private let logger = Logger(subsystem: "com.mati10p.truedepthprobe", category: "transport")
    private let sessionID = UUID().uuidString
    let logURL: URL
    private var listener: NWListener?
    private var control: ((String) -> [String: Any])?
    private var clients: [UUID: Client] = [:]

    private final class Client {
        let id = UUID()
        let connection: NWConnection
        var timer: DispatchWorkItem?
        var requestID: UInt64 = 0
        init(_ connection: NWConnection) { self.connection = connection }
    }

    init() {
        logURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("transport-\(sessionID).jsonl")
        FileManager.default.createFile(atPath: logURL.path, contents: Data())
    }

    private func log(_ event: String, _ client: Client? = nil, _ fields: [String: Any] = [:]) {
        var record = fields
        record["event"] = event
        record["session_id"] = sessionID
        record["uptime_s"] = ProcessInfo.processInfo.systemUptime
        record["utc"] = ISO8601DateFormatter().string(from: Date())
        if let client = client {
            record["connection_id"] = client.id.uuidString
            record["request_id"] = client.requestID
        }
        guard var data = try? JSONSerialization.data(withJSONObject: record, options: [.sortedKeys]),
              let text = String(data: data, encoding: .utf8) else { return }
        data.append(10)
        logger.info("\(text, privacy: .public)")
        logQueue.async {
            do {
                let handle = try FileHandle(forWritingTo: self.logURL)
                defer { try? handle.close() }
                try handle.seekToEnd(); try handle.write(contentsOf: data)
            } catch { self.logger.error("Transport log: \(error.localizedDescription, privacy: .public)") }
        }
    }

    private func close(_ client: Client, _ reason: String) {
        guard clients.removeValue(forKey: client.id) != nil else { return }
        log("connection_closed", client, ["reason": reason])
        client.timer?.cancel(); client.timer = nil
        client.connection.stateUpdateHandler = nil
        client.connection.cancel()
    }

    // Deadline is per idle/request phase, never a fixed lifetime for the connection.
    private func arm(_ client: Client) {
        client.timer?.cancel()
        let timer = DispatchWorkItem { [weak self, weak client] in
            if let self = self, let client = client { self.close(client, "phase_timeout") }
        }
        client.timer = timer
        networkQueue.asyncAfter(deadline: .now() + 15, execute: timer)
    }

    func start(token: String, control: @escaping (String) -> [String: Any], packet: @escaping (Bool) throws -> Data, report: @escaping (String) -> Void) throws {
        self.control = control
        let tcp = NWProtocolTCP.Options()
        tcp.noDelay = true
        let server = try NWListener(using: NWParameters(tls: nil, tcp: tcp), on: 8765)
        listener = server
        server.stateUpdateHandler = { state in
            self.log("listener_state", nil, ["state": String(describing: state)])
            if case .failed(let error) = state { report("Red: \(error.localizedDescription)") }
        }
        server.newConnectionHandler = { connection in
            guard self.clients.count < 4 else {
                self.log("connection_rejected", nil, ["reason": "client_limit"])
                connection.cancel(); return
            }
            let client = Client(connection)
            self.clients[client.id] = client
            self.log("connection_accepted", client)
            connection.stateUpdateHandler = { state in
                self.log("connection_state", client, ["state": String(describing: state)])
                if case .failed(let error) = state { self.close(client, error.localizedDescription) }
            }
            connection.start(queue: self.networkQueue)
            self.arm(client)
            self.receive(client, token: token, accumulated: Data(), packet: packet, report: report)
        }
        server.start(queue: networkQueue)
    }

    private func receive(_ client: Client, token: String, accumulated: Data,
                         packet: @escaping (Bool) throws -> Data, report: @escaping (String) -> Void) {
        client.connection.receive(minimumIncompleteLength: 1, maximumLength: 128) { chunk, _, complete, error in
            guard self.clients[client.id] != nil else { return }
            var request = accumulated
            if let chunk = chunk { request.append(chunk) }
            guard error == nil, request.count <= 128 else { self.close(client, "request_read_error"); return }
            guard request.contains(10) else {
                if complete { self.close(client, "peer_closed") }
                else { self.receive(client, token: token, accumulated: request, packet: packet, report: report) }
                return
            }
            let line = String(data: request, encoding: .utf8) ?? ""
            let legacy = line == "TD1 \(token)\n"
            let parts = line.dropLast().split(separator: " ", omittingEmptySubsequences: false)
            // Dedicated authenticated, one-request control connection. Never log token.
            if parts.first == "TDF" {
                guard line.last == "\n", parts.count == 3, parts[1] == token,
                      !parts[2].contains("\n"), let control = self.control else {
                    self.close(client, "invalid_control"); return
                }
                self.preparationQueue.async {
                    let result = control(String(parts[2]))
                    var data = (try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])) ?? Data("{}".utf8)
                    data.append(10)
                    self.networkQueue.async {
                        guard self.clients[client.id] != nil else { return }
                        self.log("focus_control", client, ["command": String(parts[2])])
                        client.connection.send(content: data, completion: .contentProcessed { _ in
                            self.close(client, "control_complete")
                        })
                    }
                }
                return
            }
            if !legacy {
                guard line.last == "\n", parts.count == 3, (parts[0] == "TD2" || parts[0] == "TD3"), parts[1] == token,
                      let id = UInt64(parts[2]), id > client.requestID else {
                    self.close(client, "invalid_request"); return
                }
                client.requestID = id
            }
            self.arm(client)
            let received = ProcessInfo.processInfo.systemUptime
            let rgbd = !legacy && parts[0] == "TD3"
            self.log("request_received", client, ["mode": legacy ? "TD1" : (rgbd ? "TD3" : "TD2")])
            self.preparationQueue.async {
                let began = ProcessInfo.processInfo.systemUptime
                do {
                    let data = try packet(rgbd)
                    let prepared = ProcessInfo.processInfo.systemUptime
                    self.networkQueue.async {
                        guard self.clients[client.id] != nil else { return }
                        let sendStart = ProcessInfo.processInfo.systemUptime
                        self.log("send_started", client, ["packet_bytes": data.count,
                            "prepare_ms": (prepared - began) * 1000,
                            "queue_ms": (began - received) * 1000])
                        client.connection.send(content: data, completion: .contentProcessed { error in
                            guard self.clients[client.id] != nil else { return }
                            let finished = ProcessInfo.processInfo.systemUptime
                            guard error == nil else { self.close(client, "send_error: \(error!)"); return }
                            let telemetry: [String: Any] = [
                                "protocol": "td-telemetry/1", "session_id": self.sessionID,
                                "connection_id": client.id.uuidString, "request_id": client.requestID,
                                "request_received_uptime_s": received, "send_completed_uptime_s": finished,
                                "queue_ms": (began - received) * 1000,
                                "prepare_ms": (prepared - began) * 1000,
                                "dispatch_ms": (sendStart - prepared) * 1000,
                                "send_ms": (finished - sendStart) * 1000, "packet_bytes": data.count]
                            self.log("send_completed", client, telemetry)
                            if legacy { self.close(client, "legacy_complete"); return }
                            do {
                                let json = try JSONSerialization.data(withJSONObject: telemetry, options: [.sortedKeys])
                                var length = UInt32(json.count).bigEndian
                                var trailer = withUnsafeBytes(of: &length) { Data($0) }
                                trailer.append(json)
                                client.connection.send(content: trailer, completion: .contentProcessed { error in
                                    guard self.clients[client.id] != nil else { return }
                                    guard error == nil else { self.close(client, "telemetry_send_error"); return }
                                    self.arm(client)
                                    self.receive(client, token: token, accumulated: Data(), packet: packet, report: report)
                                })
                            } catch { self.close(client, "telemetry_encode_error") }
                        })
                    }
                } catch {
                    self.networkQueue.async {
                        report(error.localizedDescription)
                        self.close(client, "prepare_error: \(error.localizedDescription)")
                    }
                }
            }
        }
    }
}
