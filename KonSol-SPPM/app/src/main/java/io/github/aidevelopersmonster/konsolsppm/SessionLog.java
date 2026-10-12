package io.github.aidevelopersmonster.konsolsppm;

/**
 * Bounded in-memory TX/RX journal (FR-03, section 4 and NFR "memory").
 * Keeps at most {@link #MAX_ENTRIES} entries; the oldest are dropped first so a
 * long exchange cannot grow memory without limit. No Android types: usable from
 * plain javac unit tests.
 */
public final class SessionLog {
    public static final int MAX_ENTRIES = 2000;

    private final String[] timestamps = new String[MAX_ENTRIES];
    private final String[] kinds = new String[MAX_ENTRIES];
    private final String[] bodies = new String[MAX_ENTRIES];
    private int head;   // index of the oldest stored entry (ring buffer)
    private int size;   // number of stored entries

    /** Records one journal line. All display formatting is done by the caller. */
    public void add(String timestamp, String kind, String body) {
        if (size == MAX_ENTRIES) {                 // drop the oldest entry
            head = (head + 1) % MAX_ENTRIES;
            size--;
        }
        int slot = (head + size) % MAX_ENTRIES;
        timestamps[slot] = timestamp;
        kinds[slot] = kind;
        bodies[slot] = body;
        size++;
    }

    public int size() { return size; }

    /** Renders one stored entry as "[HH:mm:ss.SSS] TX 4B  ...". */
    public String entryAt(int position) {
        if (position < 0 || position >= size) throw new IndexOutOfBoundsException();
        int slot = (head + position) % MAX_ENTRIES;
        return "[" + timestamps[slot] + "] " + kinds[slot] + "  " + bodies[slot];
    }

    /** Full journal text, oldest first, newline separated (used for export). */
    public String exportText() {
        StringBuilder out = new StringBuilder(size * 48);
        for (int i = 0; i < size; i++) {
            if (i > 0) out.append('\n');
            out.append(entryAt(i));
        }
        if (size > 0) out.append('\n');
        return out.toString();
    }

    public void clear() { head = 0; size = 0; }
}
