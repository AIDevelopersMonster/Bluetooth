package io.github.aidevelopersmonster.konsolsppm;

import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import android.os.Handler;
import android.os.Looper;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Arrays;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Bluetooth Classic SPP (RFCOMM) client: connect, disconnect, TX, continuous RX.
 * All socket operations run on background threads; callbacks are delivered on
 * the main (UI) thread. A connection "generation" ticket makes stale threads
 * from a previous attempt exit harmlessly, so repeated connect/disconnect and
 * abrupt link loss never block or crash the UI (FR-01, AT-09).
 */
public final class SppClient {

    /** FR-01 state machine: DISCONNECTED / CONNECTING / CONNECTED / ERROR. */
    public enum State { DISCONNECTED, CONNECTING, CONNECTED, ERROR }

    public interface Listener {
        void onState(State state, String message);
        /** Raw received bytes, exactly as read from RFCOMM — never modified. */
        void onReceive(byte[] data);
        /** Exact bytes handed to the output stream. */
        void onSent(byte[] data);
        void onError(String message);
    }

    /** Standard SPP/RFCOMM service UUID (FR-01). */
    private static final UUID SPP_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");

    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService sendQueue = Executors.newSingleThreadExecutor();
    private final Object gate = new Object();
    private final Object outputGate = new Object();
    private final Listener listener;

    private BluetoothSocket socket;
    private State state = State.DISCONNECTED;
    private int generation;
    private boolean closed;

    public SppClient(Listener listener) { this.listener = listener; }

    public boolean isConnected() {
        synchronized (gate) { return !closed && state == State.CONNECTED; }
    }

    public void connect(BluetoothDevice device) {
        final int ticket;
        synchronized (gate) {
            if (closed) return;
            generation++;
            closeQuietly(socket);
            socket = null;
            state = State.CONNECTING;
            ticket = generation;
        }
        dispatchState(State.CONNECTING, "Подключение RFCOMM...");
        new Thread(() -> receiveLoop(device, ticket), "KonSol-SPPM-RX").start();
    }

    private void receiveLoop(BluetoothDevice device, int ticket) {
        BluetoothSocket local = null;
        try {
            local = device.createRfcommSocketToServiceRecord(SPP_UUID);
            synchronized (gate) {
                if (closed || ticket != generation) return;
                socket = local;
            }
            local.connect();
            synchronized (gate) {
                if (closed || ticket != generation) return;
                state = State.CONNECTED;
            }
            dispatchState(State.CONNECTED, "SPP/RFCOMM подключён");

            InputStream input = local.getInputStream();
            byte[] buffer = new byte[1024];
            while (isCurrent(ticket)) {
                int count = input.read(buffer);   // blocking read on background thread
                if (count < 0) break;
                if (count > 0) {
                    byte[] packet = Arrays.copyOf(buffer, count);
                    ui.post(() -> listener.onReceive(packet));
                }
            }
        } catch (IOException | SecurityException ex) {
            if (isCurrent(ticket)) {
                reportError("SPP: " + ex.getClass().getSimpleName() + ": " + ex.getMessage(), ticket);
            }
        } finally {
            closeQuietly(local);
            boolean report = false;
            synchronized (gate) {
                if (!closed && ticket == generation) {
                    generation++;
                    socket = null;
                    state = State.DISCONNECTED;
                    report = true;
                }
            }
            if (report) dispatchState(State.DISCONNECTED, "RFCOMM закрыт");
        }
    }

    private boolean isCurrent(int ticket) {
        synchronized (gate) { return !closed && ticket == generation; }
    }

    /** Queue exact payload bytes for writing; refuses politely when not connected (FR-02). */
    public void send(byte[] data) {
        if (data == null || data.length == 0) { dispatchError("Нет данных для отправки"); return; }
        byte[] payload = Arrays.copyOf(data, data.length);
        final int ticket;
        final BluetoothSocket current;
        synchronized (gate) {
            if (closed || state != State.CONNECTED || socket == null) {
                dispatchError("Нет SPP-соединения — нажмите CONNECT");
                return;
            }
            ticket = generation;
            current = socket;
        }
        sendQueue.execute(() -> {
            synchronized (outputGate) {
                if (!isCurrent(ticket)) return;
                try {
                    OutputStream output = current.getOutputStream();
                    output.write(payload);
                    output.flush();
                    ui.post(() -> listener.onSent(payload));
                } catch (IOException | SecurityException ex) {
                    if (isCurrent(ticket)) {
                        dispatchError("TX: " + ex.getMessage());
                        disconnect();
                    }
                }
            }
        });
    }

    public void disconnect() {
        synchronized (gate) {
            if (closed) return;
            generation++;
            closeQuietly(socket);
            socket = null;
            state = State.DISCONNECTED;
        }
        dispatchState(State.DISCONNECTED, "Отключено");
    }

    /** Releases all resources and stops background work (called from onDestroy). */
    public void shutdown() {
        synchronized (gate) {
            if (closed) return;
            closed = true;
            generation++;
            closeQuietly(socket);
            socket = null;
            state = State.DISCONNECTED;
        }
        sendQueue.shutdownNow();
    }

    /** Marks the ERROR state, then returns the machine to DISCONNECTED for retry. */
    private void reportError(String message, int ticket) {
        boolean mark = false;
        synchronized (gate) {
            if (!closed && ticket == generation) { state = State.ERROR; mark = true; }
        }
        if (mark) {
            dispatchState(State.ERROR, "Ошибка соединения");
            dispatchError(message);
        }
    }

    private void dispatchState(State s, String message) { ui.post(() -> listener.onState(s, message)); }
    private void dispatchError(String message) { ui.post(() -> listener.onError(message)); }

    private static void closeQuietly(BluetoothSocket s) {
        if (s != null) { try { s.close(); } catch (IOException ignored) { } }
    }
}
