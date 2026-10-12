package io.github.aidevelopersmonster.konsolsppm;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;

/**
 * Reassembles UTF-8 text from a byte stream (RFCOMM is stream-oriented).
 * A multi-byte character split across two consecutive socket reads is held
 * in the internal buffer until its continuation arrives, so journal display
 * never shows corrupted half-characters. Raw bytes are always preserved by
 * the caller independently of this decoder.
 */
public final class Utf8StreamDecoder {
    private static final int MAX_PENDING = 4; // max UTF-8 sequence length
    private final ByteArrayOutputStream pending = new ByteArrayOutputStream(MAX_PENDING);

    /** Decodes as much complete UTF-8 text as possible; keeps trailing partial sequence. */
    public String decode(byte[] data, int offset, int length) {
        for (int i = offset; i < offset + length; i++) pending.write(data[i]);

        byte[] buf = pending.toByteArray();
        int safeEnd = findSafeEnd(buf, buf.length);

        if (safeEnd <= 0) return ""; // everything still incomplete (or garbage tail)

        String text = new String(buf, 0, safeEnd, StandardCharsets.UTF_8);

        // Remove consumed bytes, keep only the incomplete tail.
        byte[] rest = new byte[buf.length - safeEnd];
        System.arraycopy(buf, safeEnd, rest, 0, rest.length);
        pending.reset();
        pending.write(rest, 0, rest.length);
        return text;
    }

    /** Flushes any dangling bytes (e.g. at disconnect) as best-effort replacement text. */
    public String flush() {
        byte[] buf = pending.toByteArray();
        pending.reset();
        return new String(buf, StandardCharsets.UTF_8);
    }

    /**
     * Returns the largest prefix length that contains no truncated multi-byte
     * sequence. Scans back at most MAX_PENDING-1 bytes from the end.
     */
    private static int findSafeEnd(byte[] buf, int len) {
        int limit = Math.min(len, MAX_PENDING - 1);
        for (int back = 0; back <= limit; back++) {
            int i = len - 1 - back;
            if (i < 0) break;
            int b = buf[i] & 0xFF;
            if ((b & 0x80) == 0) return len;          // plain ASCII byte ends the buffer
            if ((b & 0xC0) == 0xC0) {                 // sequence start byte found
                int need = expectedLength(b);
                int have = len - i;
                return have >= need ? len : i;        // complete -> all safe; else cut here
            }
            // else: continuation byte 0x80..0xBF, keep scanning backwards
        }
        return len; // no start byte nearby: treat as complete (invalid bytes pass through)
    }

    private static int expectedLength(int leadByte) {
        if ((leadByte & 0xE0) == 0xC0) return 2;
        if ((leadByte & 0xF0) == 0xE0) return 3;
        if ((leadByte & 0xF8) == 0xF0) return 4;
        return 1; // invalid lead byte: pass it through immediately
    }
}
