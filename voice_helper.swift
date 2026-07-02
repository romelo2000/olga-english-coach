import AVFoundation
import Foundation
import Speech

struct TranscriptionPayload: Encodable {
    let transcript: String
    let speechSeconds: Double
    let confidence: Double
    let segmentCount: Int
}

enum VoiceHelperError: Error {
    case speechUnavailable
    case microphoneDenied
    case speechDenied
    case recognizerUnavailable
    case timedOut
}

final class VoiceTranscriber {
    private let engine = AVAudioEngine()
    private var recognitionTask: SFSpeechRecognitionTask?

    func transcribe(localeIdentifier: String, seconds: TimeInterval) throws -> TranscriptionPayload {
        let speechAuth = DispatchSemaphore(value: 0)
        var speechStatus: SFSpeechRecognizerAuthorizationStatus = .notDetermined
        SFSpeechRecognizer.requestAuthorization { status in
            speechStatus = status
            speechAuth.signal()
        }
        speechAuth.wait()
        guard speechStatus == .authorized else {
            throw VoiceHelperError.speechDenied
        }

        let micAuth = DispatchSemaphore(value: 0)
        var micGranted = false
        AVCaptureDevice.requestAccess(for: .audio) { granted in
            micGranted = granted
            micAuth.signal()
        }
        micAuth.wait()
        guard micGranted else {
            throw VoiceHelperError.microphoneDenied
        }

        guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: localeIdentifier)) else {
            throw VoiceHelperError.recognizerUnavailable
        }
        guard recognizer.isAvailable else {
            throw VoiceHelperError.speechUnavailable
        }

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = false
        request.requiresOnDeviceRecognition = true

        let inputNode = engine.inputNode
        let format = inputNode.outputFormat(forBus: 0)
        inputNode.removeTap(onBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
            request.append(buffer)
        }

        engine.prepare()
        try engine.start()

        let resultSemaphore = DispatchSemaphore(value: 0)
        var finalResult: SFSpeechRecognitionResult?
        var capturedError: Error?

        recognitionTask = recognizer.recognitionTask(with: request) { result, error in
            if let result, result.isFinal {
                finalResult = result
                resultSemaphore.signal()
            } else if let error {
                capturedError = error
                resultSemaphore.signal()
            }
        }

        let deadline = DispatchTime.now() + seconds
        if resultSemaphore.wait(timeout: deadline) == .timedOut {
            stop()
            throw VoiceHelperError.timedOut
        }

        stop()
        if let capturedError {
            throw capturedError
        }
        guard let finalResult else {
            return TranscriptionPayload(transcript: "", speechSeconds: 0, confidence: 0, segmentCount: 0)
        }

        let transcript = finalResult.bestTranscription.formattedString.trimmingCharacters(in: .whitespacesAndNewlines)
        let segments = finalResult.bestTranscription.segments
        let speechSeconds: Double
        let confidence: Double
        if let first = segments.first, let last = segments.last {
            speechSeconds = max(0.1, (last.timestamp + last.duration) - first.timestamp)
            let averageConfidence = segments.map(\.confidence).reduce(Float(0), +) / Float(max(segments.count, 1))
            confidence = Double(max(Float(0), min(Float(1), averageConfidence)))
        } else {
            speechSeconds = 0
            confidence = 0
        }

        return TranscriptionPayload(
            transcript: transcript,
            speechSeconds: speechSeconds,
            confidence: Double(confidence),
            segmentCount: segments.count
        )
    }

    private func stop() {
        recognitionTask?.cancel()
        recognitionTask = nil
        engine.stop()
        engine.inputNode.removeTap(onBus: 0)
    }
}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

let args = CommandLine.arguments
guard args.count >= 4, args[1] == "transcribe" else {
    fail("Usage: voice_helper transcribe <locale> <seconds>")
}

let locale = args[2]
guard let seconds = Double(args[3]) else {
    fail("Invalid seconds value")
}

do {
    let payload = try VoiceTranscriber().transcribe(localeIdentifier: locale, seconds: seconds)
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.withoutEscapingSlashes]
    let data = try encoder.encode(payload)
    FileHandle.standardOutput.write(data)
} catch VoiceHelperError.speechDenied {
    fail("Speech recognition permission denied in macOS.")
} catch VoiceHelperError.microphoneDenied {
    fail("Microphone permission denied in macOS.")
} catch VoiceHelperError.speechUnavailable {
    fail("On-device speech recognition unavailable for this language.")
} catch VoiceHelperError.recognizerUnavailable {
    fail("Speech recognizer unavailable for this locale.")
} catch VoiceHelperError.timedOut {
    fail("Listening timed out before final recognition.")
} catch {
    fail("Voice helper error: \(error.localizedDescription)")
}
