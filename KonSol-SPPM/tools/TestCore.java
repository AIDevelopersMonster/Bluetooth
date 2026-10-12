package io.github.aidevelopersmonster.konsolsppm;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;

/**
 * Plain-JVM regression tests for the Android-independent core:
 * HexCodec, MacroCommand, SessionLog, Utf8StreamDecoder.
 * Run through tools/test-core.ps1 (Windows) or the GitHub Actions workflow.
 */
public final class TestCore {
    private static int passed;

    private static void check(boolean ok, String name) {
        if (!ok) throw new AssertionError(name);
        passed++;
        System.out.println("PASS: " + name);
    }

    public static void main(String[] args) {
        // ---- FR-02 / AT-05: HEX parsing sends exactly the entered bytes ----
        check(Arrays.equals(HexCodec.parse("AA 00 FF"), new byte[]{(byte) 0xAA, 0, (byte) 0xFF}), "hex bytes exact");
        check(Arrays.equals(HexCodec.parse("0xAA,0x00,0xFF"), new byte[]{(byte) 0xAA, 0, (byte) 0xFF}), "hex 0x/comma separators");
        check(Arrays.equals(HexCodec.parse("A50101"), new byte[]{(byte) 0xA5, 1, 1}), "hex compact");
        check(HexCodec.display(new byte[]{1, (byte) 0xFF}).equals("01 FF"), "hex display");

        boolean odd = false;
        try { HexCodec.parse("F"); } catch (IllegalArgumentException e) { odd = true; }
        check(odd, "reject odd digit count");
        boolean invalid = false;
        try { HexCodec.parse("1G"); } catch (IllegalArgumentException e) { invalid = true; }
        check(invalid, "reject invalid hex digit");
        boolean empty = false;
        try { HexCodec.parse("   "); } catch (IllegalArgumentException e) { empty = true; }
        check(empty, "reject empty hex");

        // ---- FR-02 / AT-04: TEXT with explicit line endings ----
        check(Arrays.equals(HexCodec.text("KON", "CRLF"), new byte[]{75, 79, 78, 13, 10}), "text CRLF");
        check(Arrays.equals(HexCodec.text("KON", "CR"), new byte[]{75, 79, 78, 13}), "text CR");
        check(Arrays.equals(HexCodec.text("KON", "LF"), new byte[]{75, 79, 78, 10}), "text LF");
        check(Arrays.equals(HexCodec.text("KON", "NONE"), new byte[]{75, 79, 78}), "text NONE");
        check(Arrays.equals(HexCodec.text("ПРОВЕРКА", "LF"),
            ("ПРОВЕРКА" + "\n").getBytes(StandardCharsets.UTF_8)), "text UTF-8 Cyrillic");

        // ---- FR-04 / AT-07: programmable macro buttons ----
        MacroCommand m = new MacroCommand("LED ON", "A5 01 01", true, "CRLF");
        check(Arrays.equals(m.payload(), new byte[]{(byte) 0xA5, 1, 1}), "macro HEX exact bytes");
        MacroCommand t = new MacroCommand("Запрос", "GET", false, "LF");
        check(Arrays.equals(t.payload(), new byte[]{71, 69, 84, 10}), "macro TEXT LF");

        // First installation must be completely blank — no PING/STATUS/relay defaults.
        for (int i = 0; i < MacroCommand.COUNT; i++) {
            check(MacroCommand.empty(i).isEmpty(), "slot M" + (i + 1) + " ships blank");
        }
        boolean unassigned = false;
        try { MacroCommand.empty(0).payload(); } catch (IllegalArgumentException e) { unassigned = true; }
        check(unassigned, "blank slot refuses to send");
        check(MacroCommand.COUNT == 8, "exactly eight slots");

        // ---- FR-03: journal is bounded in memory ----
        SessionLog log = new SessionLog();
        for (int i = 0; i < SessionLog.MAX_ENTRIES + 500; i++) log.add("t", "RX", "line" + i);
        check(log.size() == SessionLog.MAX_ENTRIES, "journal capped at MAX_ENTRIES");
        check(log.entryAt(0).contains("line500"), "oldest entries dropped first");
        check(log.entryAt(log.size() - 1).contains("line" + (SessionLog.MAX_ENTRIES + 499)), "newest kept");
        log.clear();
        check(log.size() == 0 && log.exportText().isEmpty(), "journal clear");

        // ---- FR-03: UTF-8 characters split across consecutive RFCOMM reads ----
        Utf8StreamDecoder dec = new Utf8StreamDecoder();
        byte[] cyrillic = "OK:ТЕСТ".getBytes(StandardCharsets.UTF_8);
        StringBuilder joined = new StringBuilder();
        // feed one byte at a time: every multi-byte char is split across reads
        for (byte b : cyrillic) joined.append(dec.decode(new byte[]{b}, 0, 1));
        joined.append(dec.flush());
        check(joined.toString().equals("OK:ТЕСТ"), "utf8 split per byte reassembles");

        Utf8StreamDecoder dec2 = new Utf8StreamDecoder();
        byte[] part1 = Arrays.copyOfRange(cyrillic, 0, 5); // ends inside 'Т'
        byte[] part2 = Arrays.copyOfRange(cyrillic, 5, cyrillic.length);
        String s1 = dec2.decode(part1, 0, part1.length);
        String s2 = dec2.decode(part2, 0, part2.length);
        check((s1 + s2).equals("OK:ТЕСТ"), "utf8 split between two reads reassembles");

        System.out.println("ALL " + passed + " CORE TESTS PASSED");
    }
}
