package io.github.aidevelopersmonster.konsolsppm;
import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.bluetooth.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.*;
import android.provider.Settings;
import android.view.View;
import android.widget.*;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.*;

public final class MainActivity extends Activity implements SppClient.Listener {
    private static final int REQUEST_CONNECT_PERMISSION=21,LOG_LIMIT=40000;
    private static final String[] EOL={"Нет","CR","LF","CRLF"};
    private final List<BluetoothDevice> paired=new ArrayList<>();
    private final StringBuilder transcript=new StringBuilder();
    private final SimpleDateFormat clock=new SimpleDateFormat("HH:mm:ss.SSS",Locale.US);
    private final Button[] macroButtons=new Button[8];
    private final MacroCommand[] macros=new MacroCommand[8];
    private Spinner deviceSpinner,modeSpinner,eolSpinner;
    private Button connectButton;
    private TextView statusView,logView;
    private ScrollView logScroll;
    private EditText inputEdit;
    private BluetoothAdapter adapter;
    private SppClient client;
    private SharedPreferences prefs;
    private SppClient.State currentState=SppClient.State.DISCONNECTED;

    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        setContentView(R.layout.activity_main);
        prefs=getSharedPreferences("konsol_sppm",MODE_PRIVATE);
        deviceSpinner=findViewById(R.id.deviceSpinner);
        modeSpinner=findViewById(R.id.modeSpinner);
        eolSpinner=findViewById(R.id.eolSpinner);
        connectButton=findViewById(R.id.connectButton);
        statusView=findViewById(R.id.statusView);
        logView=findViewById(R.id.logView);
        logScroll=findViewById(R.id.logScroll);
        inputEdit=findViewById(R.id.inputEdit);
        client=new SppClient(this);
        BluetoothManager manager=(BluetoothManager)getSystemService(Context.BLUETOOTH_SERVICE);
        adapter=manager==null?null:manager.getAdapter();
        configureSpinner(modeSpinner,new String[]{"TEXT UTF-8","HEX bytes"});
        configureSpinner(eolSpinner,EOL);
        modeSpinner.setSelection(prefs.getInt("mode",0));
        eolSpinner.setSelection(prefs.getInt("eol",3));
        modeSpinner.setOnItemSelectedListener(new SelectionListener(pos->prefs.edit().putInt("mode",pos).apply()));
        eolSpinner.setOnItemSelectedListener(new SelectionListener(pos->prefs.edit().putInt("eol",pos).apply()));
        findViewById(R.id.refreshButton).setOnClickListener(v->requirePermissionThenRefresh());
        findViewById(R.id.settingsButton).setOnClickListener(v->startActivity(new Intent(Settings.ACTION_BLUETOOTH_SETTINGS)));
        connectButton.setOnClickListener(v->toggleConnect());
        findViewById(R.id.sendButton).setOnClickListener(v->sendEntered());
        findViewById(R.id.clearButton).setOnClickListener(v->{transcript.setLength(0);logView.setText("");});
        findViewById(R.id.shareButton).setOnClickListener(v->shareLog());
        macroButtons[0]=findViewById(R.id.macro1);
        macroButtons[1]=findViewById(R.id.macro2);
        macroButtons[2]=findViewById(R.id.macro3);
        macroButtons[3]=findViewById(R.id.macro4);
        macroButtons[4]=findViewById(R.id.macro5);
        macroButtons[5]=findViewById(R.id.macro6);
        macroButtons[6]=findViewById(R.id.macro7);
        macroButtons[7]=findViewById(R.id.macro8);
        findViewById(R.id.configureMacrosButton).setOnClickListener(v->chooseMacro());
        for(int i=0;i<macroButtons.length;i++){
            final int index=i;
            MacroCommand defaults=MacroCommand.defaultFor(i);
            macros[i]=new MacroCommand(
                prefs.getString("macro_label_"+i,defaults.label),
                prefs.getString("macro_command_"+i,prefs.getString("macro"+i,defaults.command)),
                prefs.getBoolean("macro_hex_"+i,false),
                prefs.getString("macro_eol_"+i,"CRLF"));
            updateMacroLabel(i);
            macroButtons[i].setOnClickListener(v->sendMacro(index));
            macroButtons[i].setOnLongClickListener(v->{editMacro(index);return true;});
        }
        statusView.setText("● Отключено");
        append("SYS","Classic SPP terminal ready; BLE GATT is not supported");
        requirePermissionThenRefresh();
    }

    @Override protected void onResume(){super.onResume();if(adapter!=null&&hasConnectPermission())refreshPairedDevices();}
    @Override protected void onDestroy(){client.shutdown();super.onDestroy();}
    private void configureSpinner(Spinner spinner,String[] values){
        ArrayAdapter<String> a=new ArrayAdapter<>(this,android.R.layout.simple_spinner_item,Arrays.asList(values));
        a.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinner.setAdapter(a);
    }
    private boolean hasConnectPermission(){
        return Build.VERSION.SDK_INT<Build.VERSION_CODES.S||
            checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)==PackageManager.PERMISSION_GRANTED;
    }
    private void requirePermissionThenRefresh(){
        if(adapter==null){append("SYS","Bluetooth adapter missing");setStatus("● Bluetooth отсутствует","#FF9C9C");return;}
        if(!hasConnectPermission()){requestPermissions(new String[]{Manifest.permission.BLUETOOTH_CONNECT},REQUEST_CONNECT_PERMISSION);return;}
        refreshPairedDevices();
    }
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] results){
        super.onRequestPermissionsResult(code,permissions,results);
        if(code!=REQUEST_CONNECT_PERMISSION)return;
        if(results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED)refreshPairedDevices();
        else{append("SYS","Bluetooth CONNECT permission denied");setStatus("● Нужен доступ Nearby devices","#FF9C9C");}
    }
    private void refreshPairedDevices(){
        if(adapter==null||!hasConnectPermission())return;
        try{
            if(!adapter.isEnabled()){
                paired.clear();configureSpinner(deviceSpinner,new String[]{"Bluetooth выключен"});
                setStatus("● Включите Bluetooth телефона","#FFBF69");return;
            }
            Set<BluetoothDevice> bonded=adapter.getBondedDevices();
            paired.clear();if(bonded!=null)paired.addAll(bonded);
            paired.sort(Comparator.comparing(d->(d.getName()==null?"":d.getName()).toLowerCase(Locale.ROOT)));
            if(paired.isEmpty()){
                configureSpinner(deviceSpinner,new String[]{"Нет сопряжённых устройств — Bluetooth: пара"});
                return;
            }
            List<String> names=new ArrayList<>();
            int selected=0;
            String previous=prefs.getString("selected_address","");
            for(int i=0;i<paired.size();i++){
                BluetoothDevice d=paired.get(i);
                names.add((d.getName()==null?"(no name)":d.getName())+" • "+d.getAddress());
                if(previous.equalsIgnoreCase(d.getAddress()))selected=i;
            }
            configureSpinner(deviceSpinner,names.toArray(new String[0]));
            deviceSpinner.setSelection(selected);
        }catch(SecurityException e){onError("Bluetooth permissions: "+e.getMessage());}
    }
    private void toggleConnect(){
        if(currentState!=SppClient.State.DISCONNECTED){client.disconnect();return;}
        if(!hasConnectPermission()){requirePermissionThenRefresh();return;}
        if(adapter==null||!adapter.isEnabled()){onError("Включите Bluetooth телефона");return;}
        int index=deviceSpinner.getSelectedItemPosition();
        if(index<0||index>=paired.size()){
            onError("Сначала сопрягите Classic Bluetooth в настройках Android");return;
        }
        BluetoothDevice d=paired.get(index);
        try{
            prefs.edit().putString("selected_address",d.getAddress()).apply();
            append("SYS","SPP → "+d.getName()+" / "+d.getAddress());client.connect(d);
        }catch(SecurityException e){onError("Bluetooth CONNECT: "+e.getMessage());}
    }
    private String eol(){int p=eolSpinner.getSelectedItemPosition();return p>=0&&p<EOL.length?EOL[p]:"CRLF";}
    private void sendEntered(){
        String val=inputEdit.getText().toString();
        try{client.send(modeSpinner.getSelectedItemPosition()==1?HexCodec.parse(val):HexCodec.text(val,eol()));}
        catch(IllegalArgumentException e){onError(e.getMessage());}
    }
    private void sendMacro(int i){
        try {
            byte[] data=macros[i].payload();
            client.send(data);
        } catch(IllegalArgumentException error) {
            onError("M"+(i+1)+": "+error.getMessage());
        }
    }
    private void chooseMacro() {
        String[] items=new String[macroButtons.length];
        for(int i=0;i<items.length;i++)items[i]="M"+(i+1)+" — "+macros[i].label;
        new AlertDialog.Builder(this).setTitle("Назначить кнопку")
            .setItems(items,(dialog,index)->editMacro(index))
            .setNegativeButton("Отмена",null).show();
    }
    private void editMacro(int i) {
        MacroCommand current=macros[i];
        LinearLayout form=new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        int inset=(int)(20*getResources().getDisplayMetrics().density);
        form.setPadding(inset,8,inset,8);
        EditText label=new EditText(this);
        label.setSingleLine(true);
        label.setHint("Название кнопки");
        label.setText(current.label);
        form.addView(label);
        EditText command=new EditText(this);
        command.setSingleLine(false);
        command.setMinLines(2);
        command.setHint("Команда, отправляемая при нажатии");
        command.setText(current.command);
        form.addView(command);
        Spinner encoding=new Spinner(this);
        configureSpinner(encoding,new String[]{"TEXT UTF-8","HEX байты"});
        encoding.setSelection(current.hex?1:0);
        form.addView(encoding);
        Spinner ending=new Spinner(this);
        configureSpinner(ending,EOL);
        int initial=Arrays.asList(EOL).indexOf(current.eol);
        ending.setSelection(initial<0?3:initial);
        form.addView(ending);
        AlertDialog dialog=new AlertDialog.Builder(this)
            .setTitle("Настройка M"+(i+1))
            .setView(form)
            .setNegativeButton("Отмена",null)
            .setPositiveButton("Сохранить",null)
            .create();
        dialog.setOnShowListener(ignored->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            String name=label.getText().toString().trim();
            if(name.isEmpty())name="M"+(i+1);
            if(name.length()>24)name=name.substring(0,24);
            MacroCommand updated=new MacroCommand(
                name,command.getText().toString(),
                encoding.getSelectedItemPosition()==1,
                EOL[ending.getSelectedItemPosition()]);
            if(!updated.command.isEmpty()){
                try{updated.payload();}catch(IllegalArgumentException error){onError(error.getMessage());return;}
            }
            macros[i]=updated;
            prefs.edit()
                .putString("macro_label_"+i,updated.label)
                .putString("macro_command_"+i,updated.command)
                .putBoolean("macro_hex_"+i,updated.hex)
                .putString("macro_eol_"+i,updated.eol)
                .apply();
            updateMacroLabel(i);
            dialog.dismiss();
        }));
        dialog.show();
    }
    private void updateMacroLabel(int i) {
        String name=macros[i].label;
        String caption=name.length()>10?name.substring(0,10)+"…":name;
        macroButtons[i].setText(caption);
        macroButtons[i].setContentDescription(
            "M"+(i+1)+" "+name+": "+(macros[i].hex?"HEX":"TEXT")+
            "; долгое нажатие — настроить");
        macroButtons[i].setEnabled(!macros[i].command.isEmpty());
        macroButtons[i].setAlpha(macros[i].command.isEmpty()?0.55f:1.0f);
    }
    private void shareLog(){
        Intent send=new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_SUBJECT,"KonSol-SPPM session");
        send.putExtra(Intent.EXTRA_TEXT,transcript.toString());
        startActivity(Intent.createChooser(send,"Поделиться журналом"));
    }
    private void setStatus(String text,String color){
        statusView.setText(text);statusView.setTextColor(Color.parseColor(color));
    }
    private void append(String kind,String message){
        transcript.append("[").append(clock.format(new Date())).append("] ")
            .append(kind).append("  ").append(message).append('\n');
        if(transcript.length()>LOG_LIMIT){
            int n=transcript.length()-LOG_LIMIT,cut=transcript.indexOf("\n",n);
            transcript.delete(0,cut<0?n:cut+1);
        }
        logView.setText(transcript.toString());
        logScroll.post(()->logScroll.fullScroll(View.FOCUS_DOWN));
    }
    private String displayBytes(byte[] data){
        if(modeSpinner.getSelectedItemPosition()==1)return HexCodec.display(data);
        return new String(data,StandardCharsets.UTF_8)
            .replace("\r","\\r").replace("\n","\\n").replace("\t","\\t");
    }
    @Override public void onState(SppClient.State state,String message){
        currentState=state;
        switch(state){
            case CONNECTED:
                setStatus("● "+message,"#65E6A4");connectButton.setText("DISCONNECT");break;
            case CONNECTING:
                setStatus("● "+message,"#FFBF69");connectButton.setText("CANCEL");break;
            default:
                setStatus("● "+message,"#FFBF69");connectButton.setText("CONNECT");
        }append("SYS",message);
    }
    @Override public void onReceive(byte[] data){append("RX "+data.length+"B",displayBytes(data));}
    @Override public void onSent(byte[] data){append("TX "+data.length+"B",displayBytes(data));}
    @Override public void onError(String message){
        append("ERROR",message);
        Toast.makeText(this,message,Toast.LENGTH_LONG).show();
    }
    private static final class SelectionListener implements android.widget.AdapterView.OnItemSelectedListener{
        interface Change{void selected(int index);}
        private final Change callback;
        SelectionListener(Change callback){this.callback=callback;}
        @Override public void onItemSelected(android.widget.AdapterView<?> parent,View view,int position,long id){callback.selected(position);}
        @Override public void onNothingSelected(android.widget.AdapterView<?> parent){}
    }
}
