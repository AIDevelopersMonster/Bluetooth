package io.github.aidevelopersmonster.konsolsppm;

/**
 * One persistent, user-assignable SPP command button (M1-M8).
 * Independent of the interactive terminal's TEXT/HEX and EOL settings.
 * On a first installation every slot is blank: no equipment commands
 * (PING/STATUS/relay codes and so on) are embedded in the source (FR-04).
 * No Android SDK types are used so it can be unit-tested with javac.
 */
public final class MacroCommand {
    public static final int COUNT = 8;

    /** Allowed line endings, canonical order for UI spinners. */
    public static final String EOL_NONE = "NONE";
    public static final String EOL_CR = "CR";
    public static final String EOL_LF = "LF";
    public static final String EOL_CRLF = "CRLF";
    public static final String[] EOLS = {EOL_NONE, EOL_CR, EOL_LF, EOL_CRLF};

    public final String label;
    public final String command;
    public final boolean hex;
    public final String eol;

    public MacroCommand(String label, String command, boolean hex, String eol) {
        this.label = label == null ? "" : label.trim();
        this.command = command == null ? "" : command;
        this.hex = hex;
        this.eol = eol == null ? EOL_CRLF : eol;
    }

    /** True when the user has not assigned any command to this slot yet. */
    public boolean isEmpty() { return command.trim().isEmpty(); }

    /** Exact bytes to put on the RFCOMM stream. HEX sends precisely the given bytes. */
    public byte[] payload() {
        if (isEmpty()) throw new IllegalArgumentException("Команда не назначена");
        if (hex) return HexCodec.parse(command);
        return HexCodec.text(command, eol);
    }

    /** Blank factory slot — deliberately contains no command. */
    public static MacroCommand empty(int index) {
        if (index < 0 || index >= COUNT) throw new IllegalArgumentException("Invalid button index");
        return new MacroCommand("M" + (index + 1), "", false, EOL_CRLF);
    }
}
