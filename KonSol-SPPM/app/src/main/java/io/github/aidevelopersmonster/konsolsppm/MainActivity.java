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
    private static final String[] PRESET={"HELLO","PING","STATUS","?"};
    private final List<BluetoothDevice> paired=new ArrayList<>();
    private final StringBuilder transcript=new StringBuilder();
    private final SimpleDateFormat clock=new SimpleDateFormat("HH:mm:ss.SSS",Locale.US);
    private final Button[] macroButtons=new Button[4];
    private final String[] macros=new String[4];
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
        for(int i=0;i<macroButtons.length;i++){
            final int index=i;
            macros[i]=prefs.getString("macro"+i,PRESET[i]);
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
    private void sendMacro(int i){client.send(HexCodec.text(macros[i],eol()));}
    private void editMacro(int i){
        EditText field=new EditText(this);field.setSingleLine(true);field.setText(macros[i]);
        new AlertDialog.Builder(this).setTitle("Команда M"+(i+1)+" (UTF-8)")
            .setView(field).setNegativeButton("Отмена",null)
            .setPositiveButton("Сохранить",(dialog,which)->{
                macros[i]=field.getText().toString();
                prefs.edit().putString("macro"+i,macros[i]).apply();updateMacroLabel(i);
            }).show();
    }
    private void updateMacroLabel(int i){
        String text=macros[i].length()>7?macros[i].substring(0,7)+"…":macros[i];
        macroButtons[i].setText("M"+(i+1)+" "+text);
        macroButtons[i].setContentDescription("Отправить "+macros[i]+"; долгое нажатие — настройка");
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
