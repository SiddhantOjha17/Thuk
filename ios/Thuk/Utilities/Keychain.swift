import Foundation
import Security

/// Keychain wrapper for secure token storage.
/// App Group access group is added only when the Share Extension target is configured.
enum Keychain {
    private static let service = "com.siddhant.thuk"

    static func set(_ value: String, key: String) {
        let data = Data(value.utf8)
        SecItemDelete(query(key: key) as CFDictionary)
        var item = query(key: key)
        item[kSecValueData as String] = data
        SecItemAdd(item as CFDictionary, nil)
    }

    static func get(_ key: String) -> String? {
        var q = query(key: key)
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func delete(_ key: String) {
        SecItemDelete(query(key: key) as CFDictionary)
    }

    static func clearAll() {
        for key in ["access_token", "refresh_token", "user_name", "user_email"] {
            delete(key)
        }
    }

    private static func query(key: String) -> [String: Any] {
        [
            kSecClass as String:       kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
    }
}
