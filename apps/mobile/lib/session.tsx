import React, {createContext, useContext, useEffect, useMemo, useState} from "react";
import * as SecureStore from "expo-secure-store";
import {SessionResponse, SignalChordClient} from "@signalchord/api-client";

const CONFIGURED_API_URL = process.env.EXPO_PUBLIC_API_URL ?? "";
const SESSION_KEY = "signalchord.mobile.session.v1";
const API_URL_KEY = "signalchord.mobile.api-url.v1";
const CACHE_PREFIX = "signalchord.mobile.cache.";
const UNCONFIGURED_API_URL = "https://signalchord.invalid";

function normalizeApiUrl(value: string): string {
  const normalized = value.trim().replace(/\/+$/, "");
  if (!normalized) {
    throw new Error("Server URL is required");
  }

  const parsed = new URL(normalized);
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    throw new Error("Server URL must use http or https");
  }
  return parsed.toString().replace(/\/+$/, "");
}

type ContextValue = {
  ready: boolean;
  session: SessionResponse | null;
  apiUrl: string;
  client: SignalChordClient;
  signIn(email: string, password: string, organizationSlug: string, apiUrl: string): Promise<void>;
  signOut(): Promise<void>;
  setApiUrl(value: string): Promise<void>;
  cache<T>(key: string, value: T): Promise<void>;
  cached<T>(key: string): Promise<T | null>;
};

const Context = createContext<ContextValue | null>(null);

export function SessionProvider({children}: {children: React.ReactNode}) {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [apiUrl, setApiUrlState] = useState(CONFIGURED_API_URL.trim());
  const client = useMemo(
    () => new SignalChordClient(apiUrl || UNCONFIGURED_API_URL, session?.access_token),
    [apiUrl, session],
  );

  useEffect(() => {
    Promise.all([
      SecureStore.getItemAsync(SESSION_KEY),
      SecureStore.getItemAsync(API_URL_KEY),
    ])
      .then(([storedSession, storedApiUrl]) => {
        let resolvedApiUrl = "";
        for (const candidate of [storedApiUrl, CONFIGURED_API_URL]) {
          if (!candidate) continue;
          try {
            resolvedApiUrl = normalizeApiUrl(candidate);
            break;
          } catch {
            if (candidate === storedApiUrl) {
              void SecureStore.deleteItemAsync(API_URL_KEY);
            }
          }
        }

        if (resolvedApiUrl) {
          setApiUrlState(resolvedApiUrl);
        }

        if (storedSession && resolvedApiUrl) {
          try {
            setSession(JSON.parse(storedSession) as SessionResponse);
          } catch {
            void SecureStore.deleteItemAsync(SESSION_KEY);
          }
        } else if (storedSession) {
          void SecureStore.deleteItemAsync(SESSION_KEY);
        }
      })
      .finally(() => setReady(true));
  }, []);

  const setApiUrl = async (value: string) => {
    const next = normalizeApiUrl(value);
    await SecureStore.setItemAsync(API_URL_KEY, next, {
      keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    });
    setApiUrlState(next);
  };

  const signIn = async (
    email: string,
    password: string,
    organizationSlug: string,
    serverUrl: string,
  ) => {
    const nextApiUrl = normalizeApiUrl(serverUrl);
    const next = await new SignalChordClient(nextApiUrl).createSession(
      email,
      password,
      organizationSlug,
    );
    await Promise.all([
      SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(next), {
        keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
      }),
      SecureStore.setItemAsync(API_URL_KEY, nextApiUrl, {
        keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
      }),
    ]);
    setApiUrlState(nextApiUrl);
    setSession(next);
  };

  const signOut = async () => {
    await SecureStore.deleteItemAsync(SESSION_KEY);
    setSession(null);
  };

  const cache = async <T,>(key: string, value: T) => {
    const serialized = JSON.stringify({storedAt: new Date().toISOString(), value});
    if (serialized.length <= 64000) {
      await SecureStore.setItemAsync(`${CACHE_PREFIX}${key}`, serialized);
    }
  };

  const cached = async <T,>(key: string): Promise<T | null> => {
    const value = await SecureStore.getItemAsync(`${CACHE_PREFIX}${key}`);
    if (!value) return null;
    try {
      const envelope = JSON.parse(value) as {storedAt: string; value: T};
      return Date.now() - Date.parse(envelope.storedAt) <= 604800000 ? envelope.value : null;
    } catch {
      return null;
    }
  };

  return (
    <Context.Provider
      value={{ready, session, apiUrl, client, signIn, signOut, setApiUrl, cache, cached}}
    >
      {children}
    </Context.Provider>
  );
}

export function useSession() {
  const value = useContext(Context);
  if (!value) throw new Error("SessionProvider is missing");
  return value;
}
