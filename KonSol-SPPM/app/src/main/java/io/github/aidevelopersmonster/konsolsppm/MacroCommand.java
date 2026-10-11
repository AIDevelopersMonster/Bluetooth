package io.github.aidevelopersmonster.konsolsppm;

/**
 * One persistent, user-assignable SPP command button.
 * Independent of the interactive terminal's TEXT/HEX and EOL settings.
 * No Android SDK types are used so it can be unit-tested with javac.
 */
public final class MacroCommand {
    public final String label;
    public final String command;
    public final boolean hex;
    public final String eol;

    public MacroCommand(String label, String command, boolean hex, String eol) {
        this.label = label == null ? "" : label.trim();
        this.command = command == null ? "" : command;
        this.hex = hex;
        this.eol = eol == null ? "CRLF" : eol;
    }

    public byte[] payload() {
        if (command.isEmpty()) {
            throw new IllegalArgumentException("Команда не назначена");
        }
        if (hex) return HexCodec.parse(command);
        return HexCodec.text(command, eol);
    }

    public static MacroCommand defaultFor(int index) {
        final String[] labels = {"PING", "STATUS", "HELP", "?", "M5", "M6", "M7", "M8"};
        final String[] commands = {"PING", "STATUS", "HELP", "?", "", "", "", ""};
        if (index < 0 || index >= labels.length) throw new IllegalArgumentException("Invalid button index");
        return new MacroCommand(labels[index], commands[index], false, "CRLF");
    }
}
