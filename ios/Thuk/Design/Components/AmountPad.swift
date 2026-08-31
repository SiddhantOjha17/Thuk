import SwiftUI

/// A custom numeric keypad for amount entry.
/// Outputs a Decimal via binding to `amountString`.
struct AmountPad: View {
    @Binding var amountString: String

    private let keys: [[String]] = [
        ["7", "8", "9"],
        ["4", "5", "6"],
        ["1", "2", "3"],
        [".", "0", "⌫"],
    ]

    var body: some View {
        VStack(spacing: 10) {
            ForEach(keys, id: \.self) { row in
                HStack(spacing: 10) {
                    ForEach(row, id: \.self) { key in
                        PadKey(label: key) { tap(key) }
                    }
                }
            }
        }
    }

    private func tap(_ key: String) {
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        switch key {
        case "⌫":
            if !amountString.isEmpty { amountString.removeLast() }
        case ".":
            guard !amountString.contains(".") else { return }
            amountString = amountString.isEmpty ? "0." : amountString + "."
        default:
            // Prevent leading zero (except "0.")
            if amountString == "0" { amountString = key; return }
            // Limit to 2 decimal places
            if let dot = amountString.firstIndex(of: ".") {
                let decimals = amountString.distance(from: dot, to: amountString.endIndex) - 1
                if decimals >= 2 { return }
            }
            amountString += key
        }
    }
}

private struct PadKey: View {
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            ZStack {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(Color.thukSurfaceHi)
                    .frame(maxWidth: .infinity)
                    .frame(height: 64)

                if label == "⌫" {
                    Image(systemName: "delete.backward")
                        .font(.system(size: 20, weight: .medium))
                        .foregroundStyle(.white)
                } else {
                    Text(label)
                        .font(.system(size: 24, weight: .medium, design: .rounded))
                        .foregroundStyle(.white)
                }
            }
        }
        .buttonStyle(.plain)
    }
}
