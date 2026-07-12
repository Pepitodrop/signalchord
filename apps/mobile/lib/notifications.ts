import * as Notifications from "expo-notifications";
import {Platform} from "react-native";
Notifications.setNotificationHandler({handleNotification:async()=>({shouldShowBanner:true,shouldShowList:true,shouldPlaySound:false,shouldSetBadge:true})});
export async function registerForPushNotifications():Promise<string|null>{const current=await Notifications.getPermissionsAsync();const permission=current.status==="granted"?current:await Notifications.requestPermissionsAsync();if(permission.status!=="granted")return null;if(Platform.OS==="android")await Notifications.setNotificationChannelAsync("alerts",{name:"Intelligence alerts",importance:Notifications.AndroidImportance.HIGH});try{return(await Notifications.getExpoPushTokenAsync()).data;}catch{return null;}}
