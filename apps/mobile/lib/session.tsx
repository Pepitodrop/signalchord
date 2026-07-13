import React, {createContext, useContext, useEffect, useMemo, useState} from "react";
import * as SecureStore from "expo-secure-store";
import {SessionResponse, SignalChordClient} from "@signalchord/api-client";

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:3000";
const SESSION_KEY = "signalchord.mobile.session.v1";
const CACHE_PREFIX = "signalchord.mobile.cache.";
type ContextValue={ready:boolean;session:SessionResponse|null;client:SignalChordClient;signIn(email:string,password:string,organizationSlug:string):Promise<void>;signOut():Promise<void>;cache<T>(key:string,value:T):Promise<void>;cached<T>(key:string):Promise<T|null>};
const Context=createContext<ContextValue|null>(null);

export function SessionProvider({children}:{children:React.ReactNode}){
  const[ready,setReady]=useState(false);const[session,setSession]=useState<SessionResponse|null>(null);const client=useMemo(()=>new SignalChordClient(API_URL,session?.access_token),[session]);
  useEffect(()=>{SecureStore.getItemAsync(SESSION_KEY).then(value=>setSession(value?JSON.parse(value) as SessionResponse:null)).finally(()=>setReady(true));},[]);
  const signIn=async(email:string,password:string,organizationSlug:string)=>{const next=await new SignalChordClient(API_URL).createSession(email,password,organizationSlug);await SecureStore.setItemAsync(SESSION_KEY,JSON.stringify(next),{keychainAccessible:SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY});setSession(next);};
  const signOut=async()=>{await SecureStore.deleteItemAsync(SESSION_KEY);setSession(null);};
  const cache=async<T,>(key:string,value:T)=>{const serialized=JSON.stringify({storedAt:new Date().toISOString(),value});if(serialized.length<=64000)await SecureStore.setItemAsync(`${CACHE_PREFIX}${key}`,serialized);};
  const cached=async<T,>(key:string):Promise<T|null>=>{const value=await SecureStore.getItemAsync(`${CACHE_PREFIX}${key}`);if(!value)return null;try{const envelope=JSON.parse(value) as {storedAt:string;value:T};return Date.now()-Date.parse(envelope.storedAt)<=604800000?envelope.value:null;}catch{return null;}};
  return <Context.Provider value={{ready,session,client,signIn,signOut,cache,cached}}>{children}</Context.Provider>;
}
export function useSession(){const value=useContext(Context);if(!value)throw new Error("SessionProvider is missing");return value;}
