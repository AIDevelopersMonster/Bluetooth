package io.github.aidevelopersmonster.konsolsppm;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * KonSol-SPPM main screen: paired-device selection, CONNECT/DISCONNECT,
 * TX/RX journal, manual TEXT/HEX input and eight programmable buttons M1-M8.
 * All Bluetooth I/O is delegated to SppClient background threads; this class
 * only runs on the UI thread (FR-05, section 5).
 */
public final class MainActivity extends Activity implements SppClient.Listener {

    private static final int REQUEST_CONNECT_PERMISSION = 21;
    /** Human-readable line ending captions, in MacroCommand.EOLS order. */
    private static final String[] EOL_LABELS = {"NONE", "CR", "LF", "CRLF"};

    private final List<BluetoothDevice> paired = new ArrayList<>();
    private final SimpleDateFormat clock = new SimpleDateFormat("HH:mm:ss.SSS", Locale.US);
    private final Button[] macroButtons = new Button[MacroCommand.COUNT];
    private final MacroCommand[] macros = new MacroCommand[MacroCommand.COUNT];

    private final SessionLog journal = new SessionLog();
    private final Utf8StreamDecoder rxText = new Utf8StreamDecoder();

    private Spinner deviceSpinner, modeSpinner, eolSpinner, rxViewSpinner;
    private Button connectButton;
    private TextView statusView, logView;
    private ScrollView logScroll;
    private EditText inputEdit;
    private BluetoothAdapter adapter;
    private SppClient client;
    private SettingsRepository settings;
    private SppClient.State currentState = SppClient.State.DISCONNECTED;

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_main);
        settings = new SettingsRepository(this);

        deviceSpinner = findViewById(R.id.deviceSpinner);
        modeSpinner = findViewById(R.id.modeSpinner);
        eolSpinner = findViewById(R.id.eolSpinner);
        rxViewSpinner = findViewById(R.id.rxViewSpinner);
        connectButton = findViewById(R.id.connectButton);
        statusView = findViewById(R.id.statusView);
        logView = findViewById(R.id.logView);
        logScroll = findViewById(R.id.logScroll);
        inputEdit = findViewById(R.id.inputEdit);

        client = new SppClient(this);
        BluetoothManager manager = (BluetoothManager) getSystemService(BLUETOOTH_SERVICE);
        adapter = manager == null ? null : manager.getAdapter();

        configureSpinner(modeSpinner, new String[]{"TEXT UTF-8", "HEX байты"});
        configureSpinner(eolSpinner, EOL_LABELS);
        configureSpinner(rxViewSpinner, new String[]{"RX: TEXT", "RX: HEX"});
        modeSpinner.setSelection(settings.isHexMode() ? 1 : 0);
        eolSpinner.setSelection(indexOfEol(settings.getEol()));
        rxViewSpinner.setSelection(settings.isRxHexView() ? 1 : 0);
        modeSpinner.setOnItemSelectedListener(new SelectionListener(pos -> settings.setHexMode(pos == 1)));
        eolSpinner.setOnItemSelectedListener(new SelectionListener(pos -> settings.setEol(MacroCommand.EOLS[pos])));
        rxViewSpinner.setOnItemSelectedListener(new SelectionListener(pos -> settings.setRxHexView(pos == 1)));

        findViewById(R.id.refreshButton).setOnClickListener(v -> requirePermissionThenRefresh());
        findViewById(R.id.settingsButton).setOnClickListener(v -> {
            try { startActivity(new Intent(Settings.ACTION_BLUETOOTH_SETTINGS)); }
            catch (Exception e) { onError("Настройки Android: " + e.getMessage()); }
        });
        connectButton.setOnClickListener(v -> toggleConnect());
        findViewById(R.id.sendButton).setOnClickListener(v -> sendEntered());
        findViewById(R.id.clearButton).setOnClickListener(v -> {
            journal.clear();
            renderJournal();
        });
        findViewById(R.id.shareButton).setOnClickListener(v -> exportJournal());

        for (int i = 0; i < macroButtons.length; i++) {
            macroButtons[i] = findViewById(ID_MACRO[i]);
            macros[i] = settings.loadMacro(i);
            updateMacroLabel(i);
            final int index = i;
            macroButtons[i].setOnClickListener(v -> onMacroTap(index));
            macroButtons[i].setOnLongClickListener(v -> { editMacro(index); return true; });
        }
        findViewById(R.id.configureMacrosButton).setOnClickListener(v -> chooseMacro());

        statusView.setText("● Отключено");
        append("SYS", "Classic SPP терминал готов; BLE GATT не поддерживается");
        requirePermissionThenRefresh();
    }

    /** Layout ids of M1..M8 in order. */
    private static final int[] ID_MACRO = {
        R.id.macro1, R.id.macro2, R.id.macro3, R.id.macro4,
        R.id.macro5, R.id.macro6, R.id.macro7, R.id.macro8
    };

    @Override
    protected void onResume() {
        super.onResume();
        if (adapter != null && hasConnectPermission()) refreshPairedDevices();
    }

    @Override
    protected void onDestroy() {
        client.shutdown();
        super.onDestroy();
    }

    private void configureSpinner(Spinner spinner, String[] values) {
        ArrayAdapter<String> a = new ArrayAdapter<>(this,
            android.R.layout.simple_spinner_item, Arrays.asList(values));
        a.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinner.setAdapter(a);
    }

    // ---------- Bluetooth permissions (AT-02) ----------

    private boolean hasConnectPermission() {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.S ||
            checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
    }

    private void requirePermissionThenRefresh() {
        if (adapter == null) {
            append("SYS", "Bluetooth-адаптер отсутствует");
            setStatus("● Bluetooth отсутствует", "#FF9C9C");
            return;
        }
        if (!hasConnectPermission()) {
            requestPermissions(new String[]{Manifest.permission.BLUETOOTH_CONNECT}, REQUEST_CONNECT_PERMISSION);
            return;
        }
        refreshPairedDevices();
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(code, permissions, results);
        if (code != REQUEST_CONNECT_PERMISSION) return;
        if (results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) refreshPairedDevices();
        else {
            append("SYS", "Разрешение Nearby devices отклонено");
            setStatus("● Нужен доступ Nearby devices", "#FF9C9C");
        }
    }

    // ---------- Paired device list / connect (FR-01) ----------

    private void refreshPairedDevices() {
        if (adapter == null || !hasConnectPermission()) return;
        try {
            if (!adapter.isEnabled()) {
                paired.clear();
                configureSpinner(deviceSpinner, new String[]{"Bluetooth выключен"});
                setStatus("● Включите Bluetooth телефона", "#FFBF69");
                return;
            }
            Set<BluetoothDevice> bonded = adapter.getBondedDevices();
            paired.clear();
            if (bonded != null) paired.addAll(bonded);
            paired.sort(Comparator.comparing(d ->
                (safeName(d)).toLowerCase(Locale.ROOT)));
            if (paired.isEmpty()) {
                configureSpinner(deviceSpinner, new String[]{"Нет сопряжённых устройств — Bluetooth: пара"});
                return;
            }
            List<String> names = new ArrayList<>();
            int selected = 0;
            String previous = settings.getSelectedAddress();
            for (int i = 0; i < paired.size(); i++) {
                BluetoothDevice d = paired.get(i);
                names.add(safeName(d) + " • " + d.getAddress());
                if (previous.equalsIgnoreCase(d.getAddress())) selected = i;
            }
            configureSpinner(deviceSpinner, names.toArray(new String[0]));
            deviceSpinner.setSelection(selected);
        } catch (SecurityException e) {
            onError("Bluetooth разрешения: " + e.getMessage());
        }
    }

    private String safeName(BluetoothDevice d) {
        try { String n = d.getName(); return n == null ? "(без имени)" : n; }
        catch (SecurityException e) { return "(без имени)"; }
    }

    private void toggleConnect() {
        if (currentState != SppClient.State.DISCONNECTED) { client.disconnect(); return; }
        if (!hasConnectPermission()) { requirePermissionThenRefresh(); return; }
        if (adapter == null || !adapter.isEnabled()) { onError("Включите Bluetooth телефона"); return; }
        int index = deviceSpinner.getSelectedItemPosition();
        if (index < 0 || index >= paired.size()) {
            onError("Сначала сопрягите Classic Bluetooth-устройство в настройках Android");
            return;
        }
        BluetoothDevice d = paired.get(index);
        try {
            settings.setSelectedAddress(d.getAddress());
            append("SYS", "SPP → " + safeName(d) + " / " + d.getAddress());
            client.connect(d);
        } catch (SecurityException e) {
            onError("Bluetooth CONNECT: " + e.getMessage());
        }
    }

    // ---------- Manual TX (FR-02) ----------

    private String currentEol() {
        int p = eolSpinner.getSelectedItemPosition();
        return p >= 0 && p < MacroCommand.EOLS.length ? MacroCommand.EOLS[p] : MacroCommand.EOL_CRLF;
    }

    private void sendEntered() {
        String value = inputEdit.getText().toString();
        boolean hex = modeSpinner.getSelectedItemPosition() == 1;
        if (hex) {
            // HEX sends exactly the entered bytes; automatic line ending is disabled.
            try { client.send(HexCodec.parse(value)); }
            catch (IllegalArgumentException e) { onError(e.getMessage()); }
        } else {
            if (value.isEmpty()) { onError("Введите текст команды"); return; }
            client.send(HexCodec.text(value, currentEol()));
        }
    }

    // ---------- Programmable buttons (FR-04) ----------

    private void onMacroTap(int i) {
        if (macros[i].isEmpty()) { editMacro(i); return; }   // empty tap opens editor
        try {
            client.send(macros[i].payload());
        } catch (IllegalArgumentException error) {
            onError("M" + (i + 1) + ": " + error.getMessage());
        }
    }

    private void chooseMacro() {
        String[] items = new String[macroButtons.length];
        for (int i = 0; i < items.length; i++) {
            items[i] = "M" + (i + 1) + " — " + macros[i].label +
                (macros[i].isEmpty() ? " (свободно)" : "");
        }
        new AlertDialog.Builder(this).setTitle("Назначить кнопку")
            .setItems(items, (dialog, index) -> editMacro(index))
            .setNegativeButton("Отмена", null).show();
    }

    private void editMacro(int i) {
        MacroCommand current = macros[i];
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        int inset = (int) (20 * getResources().getDisplayMetrics().density);
        form.setPadding(inset, 8, inset, 8);

        EditText label = new EditText(this);
        label.setSingleLine(true);
        label.setHint("Название кнопки");
        label.setText(current.label);
        form.addView(label);

        EditText command = new EditText(this);
        command.setSingleLine(false);
        command.setMinLines(2);
        command.setHint("Команда: текст или HEX-байты");
        command.setText(current.command);
        form.addView(command);

        Spinner encoding = new Spinner(this);
        configureSpinner(encoding, new String[]{"TEXT UTF-8", "HEX байты"});
        encoding.setSelection(current.hex ? 1 : 0);
        form.addView(encoding);

        Spinner ending = new Spinner(this);
        configureSpinner(ending, EOL_LABELS);
        int initial = indexOfEol(current.eol);
        ending.setSelection(initial < 0 ? 3 : initial);
        form.addView(ending);

        final int slot = i;
        AlertDialog dialog = new AlertDialog.Builder(this)
            .setTitle("Настройка M" + (slot + 1))
            .setView(form)
            .setNegativeButton("Отмена", null)
            .setNeutralButton("Очистить", (d2, w) -> clearMacro(slot))
            .setPositiveButton("Сохранить", null)
            .create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            String name = label.getText().toString().trim();
            if (name.isEmpty()) name = "M" + (slot + 1);
            if (name.length() > 24) name = name.substring(0, 24);
            MacroCommand updated = new MacroCommand(
                name, command.getText().toString(),
                encoding.getSelectedItemPosition() == 1,
                MacroCommand.EOLS[ending.getSelectedItemPosition()]);
            if (!updated.isEmpty()) {
                try { updated.payload(); }               // validate HEX before saving
                catch (IllegalArgumentException error) { onError(error.getMessage()); return; }
            }
            macros[slot] = updated;
            settings.saveMacro(slot, updated);
            updateMacroLabel(slot);
            dialog.dismiss();
        }));
        dialog.show();
    }

    private void clearMacro(int i) {
        macros[i] = MacroCommand.empty(i);
        settings.saveMacro(i, macros[i]);
        updateMacroLabel(i);
        append("SYS", "M" + (i + 1) + " очищена");
    }

    private void updateMacroLabel(int i) {
        MacroCommand m = macros[i];
        String name = m.label.isEmpty() ? "M" + (i + 1) : m.label;
        String caption = name.length() > 10 ? name.substring(0, 10) + "…" : name;
        macroButtons[i].setText(caption);
        macroButtons[i].setContentDescription("M" + (i + 1) + " " + name +
            (m.isEmpty() ? ": свободно — нажмите, чтобы назначить"
                        : "; формат " + (m.hex ? "HEX" : "TEXT") + ", окончание " + m.eol +
                          "; долгое нажатие — настроить"));
        macroButtons[i].setAlpha(m.isEmpty() ? 0.55f : 1.0f);
    }

    // ---------- Journal (FR-03) and export ----------

    private void exportJournal() {
        if (journal.size() == 0) { onError("Журнал пуст"); return; }
        Intent send = new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_SUBJECT, "KonSol-SPPM session");
        send.putExtra(Intent.EXTRA_TEXT, journal.exportText());
        try { startActivity(Intent.createChooser(send, "Экспорт журнала")); }
        catch (Exception e) { onError("Экспорт: нет приложения для приёма текста"); }
    }

    private void setStatus(String text, String color) {
        statusView.setText(text);
        statusView.setTextColor(Color.parseColor(color));
    }

    private void append(String kind, String message) {
        journal.add(clock.format(new Date()), kind, message);
        renderJournal();
    }

    private void renderJournal() {
        logView.setText(journal.exportText());
        logScroll.post(() -> logScroll.fullScroll(View.FOCUS_DOWN));
    }

    /** RX raw bytes are always kept intact; only display rendering depends on the view mode. */
    private String displayBytes(byte[] data) {
        if (rxViewSpinner.getSelectedItemPosition() == 1) return HexCodec.display(data);
        return printable(rxText.decode(data, 0, data.length));
    }

    private static String printable(String s) {
        return s.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t");
    }

    private static int indexOfEol(String eol) {
        for (int i = 0; i < MacroCommand.EOLS.length; i++)
            if (MacroCommand.EOLS[i].equals(eol)) return i;
        return -1;
    }

    // ---------- SppClient.Listener (UI thread callbacks) ----------

    @Override
    public void onState(SppClient.State state, String message) {
        currentState = state;
        switch (state) {
            case CONNECTED:
                setStatus("● " + message, "#65E6A4");
                connectButton.setText("DISCONNECT");
                break;
            case CONNECTING:
                setStatus("● " + message, "#FFBF69");
                connectButton.setText("CANCEL");
                break;
            case ERROR:
                setStatus("● " + message, "#FF9C9C");
                connectButton.setText("CONNECT");
                break;
            default:
                setStatus("● " + message, "#FFBF69");
                connectButton.setText("CONNECT");
                rxText.flush();
        }
        append("SYS", message);
    }

    @Override
    public void onReceive(byte[] data) {
        append("RX " + data.length + "B", displayBytes(data));
    }

    @Override
    public void onSent(byte[] data) {
        append("TX " + data.length + "B", HexCodec.display(data));
    }

    @Override
    public void onError(String message) {
        append("ERROR", message);
        Toast.makeText(this, message, Toast.LENGTH_LONG).show();
    }

    private static final class SelectionListener implements android.widget.AdapterView.OnItemSelectedListener {
        interface Change { void selected(int index); }
        private final Change callback;
        SelectionListener(Change callback) { this.callback = callback; }
        @Override public void onItemSelected(android.widget.AdapterView<?> parent, View view, int position, long id) {
            callback.selected(position);
        }
        @Override public void onNothingSelected(android.widget.AdapterView<?> parent) { }
    }
}
