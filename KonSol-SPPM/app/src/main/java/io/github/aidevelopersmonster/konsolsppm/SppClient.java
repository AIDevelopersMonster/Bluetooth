package io.github.aidevelopersmonster.konsolsppm;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import android.os.Handler;
import android.os.Looper;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;

public final class SppClient {
    public enum State {DISCONNECTED,CONNECTING,CONNECTED}
    public interface Listener {
        void onState(State state,String message);
        void onReceive(byte[] data);
        void onSent(byte[] data);
        void onError(String message);
    }
    private static final UUID SPP_UUID=UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");
    private final Handler ui=new Handler(Looper.getMainLooper());
    private final ExecutorService sendQueue=Executors.newSingleThreadExecutor();
    private final Object gate=new Object(),outputGate=new Object();
    private final Listener listener;
    private BluetoothSocket socket;
    private State state=State.DISCONNECTED;
    private int generation;
    private boolean closed;
    public SppClient(Listener listener){this.listener=listener;}
    public boolean isConnected(){synchronized(gate){return !closed&&state==State.CONNECTED;}}
    public void connect(BluetoothDevice device){
        final int ticket;
        synchronized(gate){
            if(closed)return;
            generation++;closeQuietly(socket);socket=null;
            state=State.CONNECTING;ticket=generation;
        }
        dispatchState(State.CONNECTING,"Подключение RFCOMM...");
        new Thread(()->receiveLoop(device,ticket),"KonSol-SPPM-RX").start();
    }
    private void receiveLoop(BluetoothDevice device,int ticket){
        BluetoothSocket local=null;
        try{
            local=device.createRfcommSocketToServiceRecord(SPP_UUID);
            synchronized(gate){if(closed||ticket!=generation)return;socket=local;}
            local.connect();
            synchronized(gate){if(closed||ticket!=generation)return;state=State.CONNECTED;}
            dispatchState(State.CONNECTED,"SPP/RFCOMM подключён");
            InputStream input=local.getInputStream();
            byte[] buffer=new byte[1024];
            while(isCurrent(ticket)){
                int count=input.read(buffer);
                if(count<0)break;
                if(count>0){byte[] packet=Arrays.copyOf(buffer,count);ui.post(()->listener.onReceive(packet));}
            }
        }catch(IOException|SecurityException ex){
            if(isCurrent(ticket))dispatchError("SPP: "+ex.getClass().getSimpleName()+": "+ex.getMessage());
        }finally{
            closeQuietly(local);
            boolean report=false;
            synchronized(gate){
                if(!closed&&ticket==generation){
                    generation++;socket=null;state=State.DISCONNECTED;report=true;
                }
            }
            if(report)dispatchState(State.DISCONNECTED,"RFCOMM закрыт");
        }
    }
    private boolean isCurrent(int ticket){synchronized(gate){return !closed&&ticket==generation;}}
    public void send(byte[] data){
        if(data==null||data.length==0){dispatchError("Нет данных для отправки");return;}
        byte[] payload=Arrays.copyOf(data,data.length);
        final int ticket;final BluetoothSocket current;
        synchronized(gate){
            if(closed||state!=State.CONNECTED||socket==null){dispatchError("Нет SPP-соединения");return;}
            ticket=generation;current=socket;
        }
        sendQueue.execute(()->{
            synchronized(outputGate){
                if(!isCurrent(ticket))return;
                try{
                    OutputStream output=current.getOutputStream();
                    output.write(payload);output.flush();
                    ui.post(()->listener.onSent(payload));
                }catch(IOException|SecurityException ex){
                    if(isCurrent(ticket)){dispatchError("TX: "+ex.getMessage());disconnect();}
                }
            }
        });
    }
    public void disconnect(){
        synchronized(gate){
            if(closed)return;
            generation++;closeQuietly(socket);socket=null;state=State.DISCONNECTED;
        }dispatchState(State.DISCONNECTED,"Отключено");
    }
    public void shutdown(){
        synchronized(gate){
            if(closed)return;
            closed=true;generation++;closeQuietly(socket);socket=null;state=State.DISCONNECTED;
        }sendQueue.shutdownNow();
    }
    private void dispatchState(State state,String message){ui.post(()->listener.onState(state,message));}
    private void dispatchError(String message){ui.post(()->listener.onError(message));}
    private static void closeQuietly(BluetoothSocket s){
        if(s!=null){try{s.close();}catch(IOException ignored){}}
    }
}
