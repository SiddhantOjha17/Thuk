import SwiftUI

/// A small rounded-square icon representing a category.
/// Mirrors the style of iOS Settings app icons.
struct CategoryIcon: View {
    let name: String
    let hexColor: String?
    var size: CGFloat = 36

    private var meta: CategoryMeta { CategoryMeta.find(name: name) }

    var body: some View {
        let color = hexColor.map { Color(hex: $0) } ?? meta.color
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.28, style: .continuous)
                .fill(color.opacity(0.18))
                .frame(width: size, height: size)
            Image(systemName: meta.symbol)
                .font(.system(size: size * 0.44, weight: .medium))
                .foregroundStyle(color)
        }
    }
}
