package io.github.aidevelopersmonster.konsolsppm;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * Persistent local storage for user settings (FR-04, section 4 of the specification).
 * Stores macro button assignments M1-M8, manual TX mode/line ending and the last
 * selected Bluetooth device address. Plain SharedPreferences: data survives an
 * ordinary APK update because the package's private storage is not removed.
 */
public final class SettingsRepository {
    public static final int MACRO_COUNT = MacroCommand.COUNT;

    private static final String FILE = "konsol_sppm";
    private static final String KEY_MODE = "mode";
    private static final String KEY_EOL = "eol";
    private static final String KEY_RX_VIEW = "rx_view";
    private static final String KEY_SELECTED_ADDRESS = "selected_address";
    private static final String KEY_MACRO_PREFIX = "macro_";

    private final SharedPreferences prefs;

    public SettingsRepository(Context context) {
        prefs = context.getApplicationContext().getSharedPreferences(FILE, Context.MODE_PRIVATE);
    }

    /** Manual TX display/send mode: true = HEX, false = TEXT UTF-8. */
    public boolean isHexMode() { return prefs.getBoolean(KEY_MODE, false); }
    public void setHexMode(boolean hex) { prefs.edit().putBoolean(KEY_MODE, hex).apply(); }

    /** Manual TX line ending: NONE / CR / LF / CRLF. */
    public String getEol() { return prefs.getString(KEY_EOL, MacroCommand.EOL_CRLF); }
    public void setEol(String eol) { prefs.edit().putString(KEY_EOL, eol).apply(); }

    /** RX journal rendering: true = HEX, false = TEXT UTF-8. */
    public boolean isRxHexView() { return prefs.getBoolean(KEY_RX_VIEW, false); }
    public void setRxHexView(boolean hex) { prefs.edit().putBoolean(KEY_RX_VIEW, hex).apply(); }

    /** Last chosen paired device (MAC address). */
    public String getSelectedAddress() { return prefs.getString(KEY_SELECTED_ADDRESS, ""); }
    public void setSelectedAddress(String address) {
        prefs.edit().putString(KEY_SELECTED_ADDRESS, address == null ? "" : address).apply();
    }

    /**
     * Loads one macro slot. On first installation every slot is blank:
     * no equipment commands are embedded in the application (FR-04).
     */
    public MacroCommand loadMacro(int index) {
        if (index < 0 || index >= MACRO_COUNT) throw new IllegalArgumentException("Invalid button index");
        String p = KEY_MACRO_PREFIX + index + "_";
        return new MacroCommand(
            prefs.getString(p + "label", ""),
            prefs.getString(p + "command", ""),
            prefs.getBoolean(p + "hex", false),
            prefs.getString(p + "eol", MacroCommand.EOL_CRLF));
    }

    public void saveMacro(int index, MacroCommand macro) {
        if (index < 0 || index >= MACRO_COUNT) throw new IllegalArgumentException("Invalid button index");
        String p = KEY_MACRO_PREFIX + index + "_";
        prefs.edit()
            .putString(p + "label", macro.label)
            .putString(p + "command", macro.command)
            .putBoolean(p + "hex", macro.hex)
            .putString(p + "eol", macro.eol)
            .apply();
    }
}
