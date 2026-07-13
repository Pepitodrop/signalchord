import {Stack} from "expo-router";
import {SessionProvider} from "../lib/session";
import {theme} from "../lib/theme";

export default function Layout() {
  return <SessionProvider><Stack screenOptions={{headerStyle:{backgroundColor:theme.surface},headerTintColor:theme.text,contentStyle:{backgroundColor:theme.background}}}/></SessionProvider>;
}
