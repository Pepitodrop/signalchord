import {useEffect,useState} from "react";
import {Link} from "expo-router";
import {ActivityIndicator,Platform,Pressable,SafeAreaView,ScrollView,StyleSheet,Text,TextInput,View} from "react-native";
import {AlertRecord} from "@signalchord/api-client";
import {useSession} from "../lib/session";
import {theme} from "../lib/theme";
import {registerForPushNotifications} from "../lib/notifications";

export default function Home(){
  const{ready,session,client,signIn,signOut,cache,cached}=useSession();
  const[email,setEmail]=useState("analyst@signalchord.local");
  const[password,setPassword]=useState("signalchord-demo-password");
  const[organization,setOrganization]=useState("demo");
  const[alerts,setAlerts]=useState<AlertRecord[]>([]);
  const[error,setError]=useState("");
  useEffect(()=>{
    if(!session)return;
    client.alerts().then(value=>{setAlerts(value);void cache("alerts",value);}).catch(async()=>setAlerts((await cached<AlertRecord[]>("alerts"))??[]));
    void registerForPushNotifications().then(token=>token?client.registerNotificationEndpoint(Platform.OS,token):null).catch(()=>null);
  },[session,client]);
  if(!ready)return <SafeAreaView style={s.center}><ActivityIndicator color={theme.accent}/></SafeAreaView>;
  if(!session)return <SafeAreaView style={s.root}><View style={s.login}><Text style={s.brand}>SIGNALCHORD</Text><Text style={s.title}>Connected intelligence.</Text><TextInput style={s.input} value={email} onChangeText={setEmail} autoCapitalize="none" placeholder="Email" placeholderTextColor={theme.muted}/><TextInput style={s.input} value={password} onChangeText={setPassword} secureTextEntry placeholder="Password" placeholderTextColor={theme.muted}/><TextInput style={s.input} value={organization} onChangeText={setOrganization} autoCapitalize="none" placeholder="Organization" placeholderTextColor={theme.muted}/>{error?<Text style={s.error}>{error}</Text>:null}<Pressable style={s.primary} onPress={()=>signIn(email,password,organization).catch(()=>setError("Sign-in failed"))}><Text style={s.primaryText}>Sign in</Text></Pressable></View></SafeAreaView>;
  return <SafeAreaView style={s.root}><ScrollView contentContainerStyle={s.content}><View style={s.header}><View><Text style={s.brand}>SIGNALCHORD</Text><Text style={s.title}>Live intelligence</Text></View><Pressable onPress={()=>void signOut()}><Text style={s.muted}>Sign out</Text></Pressable></View><View style={s.nav}><Link href="/alerts" asChild><Pressable style={s.navCard}><Text style={s.navTitle}>Alerts</Text><Text style={s.muted}>{alerts.length} projected</Text></Pressable></Link><Link href="/watchlists" asChild><Pressable style={s.navCard}><Text style={s.navTitle}>Watchlists</Text><Text style={s.muted}>Monitored entities</Text></Pressable></Link><Link href="/entity/company%3Aacme" asChild><Pressable style={s.navCard}><Text style={s.navTitle}>Entity graph</Text><Text style={s.muted}>Acme Corporation</Text></Pressable></Link></View><Text style={s.section}>Latest alerts</Text>{alerts.slice(0,8).map(alert=><Link key={alert.id} href={`/alert/${alert.id}`} asChild><Pressable style={s.card}><View style={{flex:1}}><Text style={s.high}>SCORE {alert.alert_score} · SEVERITY {alert.severity_code}</Text><Text style={s.cardTitle}>{alert.title}</Text><Text style={s.muted}>{alert.summary}</Text></View><Text style={s.arrow}>›</Text></Pressable></Link>)}</ScrollView></SafeAreaView>
}

const s=StyleSheet.create({root:{flex:1,backgroundColor:theme.background},center:{flex:1,alignItems:"center",justifyContent:"center",backgroundColor:theme.background},content:{padding:22,gap:12},login:{flex:1,padding:24,justifyContent:"center",gap:14},brand:{color:theme.accent,fontWeight:"800",letterSpacing:2},title:{color:theme.text,fontSize:34,fontWeight:"700",marginTop:8,marginBottom:18},input:{borderWidth:1,borderColor:theme.border,backgroundColor:theme.surface,color:theme.text,borderRadius:12,padding:14},primary:{backgroundColor:theme.accent,borderRadius:12,padding:15,alignItems:"center"},primaryText:{color:"white",fontWeight:"800"},error:{color:theme.danger},header:{flexDirection:"row",justifyContent:"space-between",alignItems:"flex-start"},nav:{flexDirection:"row",gap:10,flexWrap:"wrap"},navCard:{backgroundColor:theme.surface,borderColor:theme.border,borderWidth:1,borderRadius:15,padding:15,minWidth:"46%"},navTitle:{color:theme.text,fontWeight:"700",fontSize:16},muted:{color:theme.muted,lineHeight:20},section:{color:theme.text,fontSize:20,fontWeight:"700",marginTop:18},card:{backgroundColor:theme.surface,borderColor:theme.border,borderWidth:1,borderRadius:18,padding:18,flexDirection:"row",gap:12},high:{color:theme.danger,fontWeight:"700",fontSize:11},cardTitle:{color:theme.text,fontSize:19,fontWeight:"700",marginVertical:7},arrow:{color:theme.accent,fontSize:32}});
