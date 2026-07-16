import {useEffect, useState} from "react";
import {Link} from "expo-router";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {AlertRecord} from "@signalchord/api-client";
import {useSession} from "../lib/session";
import {theme} from "../lib/theme";
import {registerForPushNotifications} from "../lib/notifications";

export default function Home() {
  const {ready, session, apiUrl, client, signIn, signOut, cache, cached} = useSession();
  const [serverUrl, setServerUrl] = useState(apiUrl);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organization, setOrganization] = useState("");
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setServerUrl(apiUrl);
  }, [apiUrl]);

  useEffect(() => {
    if (!session) return;
    client
      .alerts()
      .then(value => {
        setAlerts(value);
        void cache("alerts", value);
      })
      .catch(async () => setAlerts((await cached<AlertRecord[]>("alerts")) ?? []));
    void registerForPushNotifications()
      .then(token => (token ? client.registerNotificationEndpoint(Platform.OS, token) : null))
      .catch(() => null);
  }, [session, client, cache, cached]);

  const submit = async () => {
    setError("");
    if (!serverUrl.trim() || !email.trim() || !password || !organization.trim()) {
      setError("Server URL, email, password, and organization are required.");
      return;
    }

    setSubmitting(true);
    try {
      await signIn(email.trim(), password, organization.trim(), serverUrl.trim());
      setPassword("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign-in failed");
    } finally {
      setSubmitting(false);
    }
  };

  if (!ready) {
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator color={theme.accent} accessibilityLabel="Loading SignalChord" />
      </SafeAreaView>
    );
  }

  if (!session) {
    return (
      <SafeAreaView style={styles.root}>
        <KeyboardAvoidingView
          style={styles.flex}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
        >
          <ScrollView
            contentContainerStyle={styles.login}
            keyboardShouldPersistTaps="handled"
          >
            <Text style={styles.brand}>SIGNALCHORD</Text>
            <Text style={styles.title}>Your self-hosted intelligence workspace.</Text>
            <Text style={styles.help}>
              Connect to the HTTPS address of your SignalChord server. Local HTTP addresses are
              also supported for private development networks.
            </Text>
            <TextInput
              style={styles.input}
              value={serverUrl}
              onChangeText={setServerUrl}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              autoComplete="url"
              placeholder="https://signalchord.example.com"
              placeholderTextColor={theme.muted}
              accessibilityLabel="Server URL"
            />
            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              autoComplete="email"
              textContentType="emailAddress"
              placeholder="Email"
              placeholderTextColor={theme.muted}
              accessibilityLabel="Email"
            />
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoComplete="password"
              textContentType="password"
              placeholder="Password"
              placeholderTextColor={theme.muted}
              accessibilityLabel="Password"
              onSubmitEditing={() => void submit()}
            />
            <TextInput
              style={styles.input}
              value={organization}
              onChangeText={setOrganization}
              autoCapitalize="none"
              autoCorrect={false}
              placeholder="Organization slug"
              placeholderTextColor={theme.muted}
              accessibilityLabel="Organization slug"
              onSubmitEditing={() => void submit()}
            />
            {error ? (
              <Text style={styles.error} accessibilityRole="alert">
                {error}
              </Text>
            ) : null}
            <Pressable
              style={[styles.primary, submitting && styles.primaryDisabled]}
              onPress={() => void submit()}
              disabled={submitting}
              accessibilityRole="button"
              accessibilityLabel="Sign in"
            >
              {submitting ? (
                <ActivityIndicator color="white" />
              ) : (
                <Text style={styles.primaryText}>Sign in</Text>
              )}
            </Pressable>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <View>
            <Text style={styles.brand}>SIGNALCHORD</Text>
            <Text style={styles.title}>Live intelligence</Text>
          </View>
          <Pressable onPress={() => void signOut()} accessibilityRole="button">
            <Text style={styles.muted}>Sign out</Text>
          </Pressable>
        </View>
        <View style={styles.nav}>
          <Link href="/alerts" asChild>
            <Pressable style={styles.navCard} accessibilityRole="button">
              <Text style={styles.navTitle}>Alerts</Text>
              <Text style={styles.muted}>{alerts.length} projected</Text>
            </Pressable>
          </Link>
          <Link href="/watchlists" asChild>
            <Pressable style={styles.navCard} accessibilityRole="button">
              <Text style={styles.navTitle}>Watchlists</Text>
              <Text style={styles.muted}>Monitored entities</Text>
            </Pressable>
          </Link>
          <Link href="/entity/company%3Aacme" asChild>
            <Pressable style={styles.navCard} accessibilityRole="button">
              <Text style={styles.navTitle}>Entity graph</Text>
              <Text style={styles.muted}>Explore relationships</Text>
            </Pressable>
          </Link>
        </View>
        <Text style={styles.section}>Latest alerts</Text>
        {alerts.slice(0, 8).map(alert => (
          <Link key={alert.id} href={`/alert/${alert.id}`} asChild>
            <Pressable style={styles.card} accessibilityRole="button">
              <View style={styles.flex}>
                <Text style={styles.high}>
                  SCORE {alert.alert_score} · SEVERITY {alert.severity_code}
                </Text>
                <Text style={styles.cardTitle}>{alert.title}</Text>
                <Text style={styles.muted}>{alert.summary}</Text>
              </View>
              <Text style={styles.arrow}>›</Text>
            </Pressable>
          </Link>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {flex: 1, backgroundColor: theme.background},
  flex: {flex: 1},
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.background,
  },
  content: {padding: 22, gap: 12},
  login: {flexGrow: 1, padding: 24, justifyContent: "center", gap: 14},
  brand: {color: theme.accent, fontWeight: "800", letterSpacing: 2},
  title: {color: theme.text, fontSize: 34, fontWeight: "700", marginTop: 8, marginBottom: 8},
  help: {color: theme.muted, lineHeight: 21, marginBottom: 10},
  input: {
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
    color: theme.text,
    borderRadius: 12,
    padding: 14,
    minHeight: 50,
  },
  primary: {
    backgroundColor: theme.accent,
    borderRadius: 12,
    padding: 15,
    minHeight: 52,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryDisabled: {opacity: 0.6},
  primaryText: {color: "white", fontWeight: "800"},
  error: {color: theme.danger},
  header: {flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start"},
  nav: {flexDirection: "row", gap: 10, flexWrap: "wrap"},
  navCard: {
    backgroundColor: theme.surface,
    borderColor: theme.border,
    borderWidth: 1,
    borderRadius: 15,
    padding: 15,
    minWidth: "46%",
    flexGrow: 1,
  },
  navTitle: {color: theme.text, fontWeight: "700", fontSize: 16},
  muted: {color: theme.muted, lineHeight: 20},
  section: {color: theme.text, fontSize: 20, fontWeight: "700", marginTop: 18},
  card: {
    backgroundColor: theme.surface,
    borderColor: theme.border,
    borderWidth: 1,
    borderRadius: 18,
    padding: 18,
    flexDirection: "row",
    gap: 12,
  },
  high: {color: theme.danger, fontWeight: "700", fontSize: 11},
  cardTitle: {color: theme.text, fontSize: 19, fontWeight: "700", marginVertical: 7},
  arrow: {color: theme.accent, fontSize: 32},
});
