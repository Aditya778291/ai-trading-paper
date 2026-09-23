declare const process: {
  env: {
    EXPO_PUBLIC_API_BASE_URL?: string;
  };
};

import React, { useEffect, useMemo, useState } from 'react';
import { SafeAreaView, View, Text, TextInput, Pressable, StyleSheet, Alert, ActivityIndicator, ScrollView, Dimensions } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import Constants from 'expo-constants';

const envUrl = String(process.env.EXPO_PUBLIC_API_BASE_URL || '');
const configuredUrl = String(Constants.expoConfig?.extra?.apiBaseUrl || '');
const API_BASE_URL = (envUrl || configuredUrl).replace(/\/$/, '');
const screenWidth = Dimensions.get('window').width;

async function api(path:string, opts:any={}, token?:string) {
  if (!API_BASE_URL || API_BASE_URL.includes('REPLACE_WITH_') || API_BASE_URL.includes('YOUR-PUBLIC')) {
    throw new Error('The API server is not configured.');
  }

  const isHttps = API_BASE_URL.startsWith('https://');
  const isLocalDev =
    __DEV__ &&
    (
      API_BASE_URL.startsWith('http://localhost:') ||
      API_BASE_URL.startsWith('http://127.0.0.1:') ||
      /^http:\/\/192\.168\.\d+\.\d+(:\d+)?$/.test(API_BASE_URL) ||
      /^http:\/\/10\.\d+\.\d+\.\d+(:\d+)?$/.test(API_BASE_URL) ||
      /^http:\/\/172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+(:\d+)?$/.test(API_BASE_URL)
    );

  if (!isHttps && !isLocalDev) {
    throw new Error('Production API must use HTTPS. For local Expo development, use your PC LAN IP over HTTP.');
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);

  try {
    const r = await fetch(API_BASE_URL + path, {
      ...opts,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(opts.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      }
    });

    const text = await r.text();
    let j:any = {};

    try {
      j = text ? JSON.parse(text) : {};
    } catch {}

    if (!r.ok) {
      throw new Error(j.detail || `Request failed (${r.status})`);
    }

    return j;
  } catch (e:any) {
    if (e?.name === 'AbortError') {
      throw new Error('Server request timed out.');
    }

    if (e?.message === 'Network request failed') {
      throw new Error('Cannot reach the trading server.');
    }

    throw e;
  } finally {
    clearTimeout(timeout);
  }
}

const money = (n:any) =>
  typeof n === 'number'
    ? `₹${n.toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })}`
    : '—';

const pct = (n:any) =>
  typeof n === 'number'
    ? `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
    : '—';

function CandlestickChart({ candles }: { candles:any[] }) {
  const data = candles.slice(-55);

  if (!data.length) {
    return (
      <View style={s.chartEmpty}>
        <Text style={s.muted}>No chart data</Text>
      </View>
    );
  }

  const max = Math.max(...data.map(x => x.high));
  const min = Math.min(...data.map(x => x.low));
  const span = Math.max(max - min, 0.000001);
  const h = 220;

  return (
    <View style={s.chart}>
      {data.map((c, i) => {
        const x = i * (screenWidth - 48) / data.length;
        const w = Math.max(3, (screenWidth - 64) / data.length - 2);
        const wickTop = (max - c.high) / span * h;
        const wickBottom = (max - c.low) / span * h;
        const bodyTop = (max - Math.max(c.open, c.close)) / span * h;
        const bodyH = Math.max(3, Math.abs(c.close - c.open) / span * h);

        return (
          <View
            key={`${c.time}-${i}`}
            style={{
              position: 'absolute',
              left: x + 5,
              width: w,
              height: h
            }}
          >
            <View
              style={{
                position: 'absolute',
                left: w / 2,
                top: wickTop,
                width: 1,
                height: Math.max(1, wickBottom - wickTop),
                backgroundColor: '#9aa6bb'
              }}
            />

            <View
              style={{
                position: 'absolute',
                left: 0,
                top: bodyTop,
                width: w,
                height: bodyH,
                borderRadius: 1,
                backgroundColor: c.close >= c.open ? '#63dcb4' : '#ff7182'
              }}
            />
          </View>
        );
      })}

      <Text style={s.chartHigh}>{max.toFixed(2)}</Text>
      <Text style={s.chartLow}>{min.toFixed(2)}</Text>
    </View>
  );
}

function MarketScreen({
  token,
  onSelect
}: {
  token:string;
  onSelect:(symbol:string)=>void;
}) {
  const [universe, setUniverse] = useState<any[]>([]);
  const [quotes, setQuotes] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const u = await api('/api/market/universe', {}, token);
      setUniverse(u);

      const symbols = u
        .slice(0, 18)
        .map((x:any) => x.symbol)
        .join(',');

      setQuotes(
        await api(
          '/api/market/quotes?symbols=' +
          encodeURIComponent(symbols),
          {},
          token
        )
      );
    } catch (e:any) {
      Alert.alert('Market data', e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (search.trim()) return;

    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [search]);

  useEffect(() => {
    const q = search.trim();

    if (!q) {
      setSearchResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        const found = await api(
          '/api/market/search?q=' + encodeURIComponent(q),
          {},
          token
        );

        const top = found.slice(0, 12);
        setSearchResults(top);

        if (top.length) {
          setQuotes(
            await api(
              '/api/market/quotes?symbols=' +
              encodeURIComponent(
                top.map((x:any) => x.symbol).join(',')
              ),
              {},
              token
            )
          );
        }
      } catch (e:any) {}
    }, 350);

    return () => clearTimeout(timer);
  }, [search, token]);

  const visible = useMemo(
    () =>
      search.trim()
        ? quotes.filter(x =>
            searchResults.some(y => y.symbol === x.symbol)
          )
        : quotes,
    [quotes, search, searchResults]
  );

  return (
    <ScrollView contentContainerStyle={s.page}>
      <View style={s.header}>
        <View>
          <Text style={s.title}>Markets</Text>
          <Text style={s.subtitle}>Live snapshot · auto refresh 5s</Text>
        </View>

        <Text style={s.live}>● LIVE</Text>
      </View>

      <TextInput
        style={s.input}
        value={search}
        onChangeText={setSearch}
        placeholder="Search NIFTY, RELIANCE, BTC..."
        placeholderTextColor="#77839a"
        autoCapitalize="characters"
      />

      <View style={s.marketHero}>
        <Text style={s.heroTitle}>Market universe</Text>
        <Text style={s.heroText}>
          {universe.length} instruments available · Indian + global indices,
          stocks, commodities, FX and crypto
        </Text>
      </View>

      {loading ? (
        <ActivityIndicator
          size="large"
          color="#63dcb4"
          style={{ marginTop: 30 }}
        />
      ) : (
        visible.map(item => (
          <Pressable
            key={item.symbol}
            style={s.marketRow}
            onPress={() => onSelect(item.symbol)}
          >
            <View style={{ flex: 1 }}>
              <Text style={s.marketName}>{item.name}</Text>
              <Text style={s.muted}>{item.symbol}</Text>
            </View>

            <View style={{ alignItems: 'flex-end' }}>
              <Text style={s.marketPrice}>
                {item.price?.toLocaleString?.('en-IN', {
                  maximumFractionDigits: 2
                }) ?? '—'}
              </Text>

              <Text style={item.change_pct >= 0 ? s.up : s.down}>
                {pct(item.change_pct)}
              </Text>
            </View>
          </Pressable>
        ))
      )}

      <Text style={s.disclaimer}>
        Default adapter: Yahoo Finance. Quotes can be delayed and depend on
        provider availability. Exchange-certified real-time feeds require an
        appropriate licensed provider.
      </Text>
    </ScrollView>
  );
}

function DetailScreen({
  token,
  symbol,
  onBack
}: {
  token:string;
  symbol:string;
  onBack:()=>void;
}) {
  const [range, setRange] = useState('1d');
  const [data, setData] = useState<any>(null);
  const [ai, setAi] = useState<any>(null);
  const [busy, setBusy] = useState(true);

  const load = async () => {
    setBusy(true);

    try {
      const [h, q] = await Promise.all([
        api(
          `/api/market/history/${encodeURIComponent(symbol)}?range=${range}`,
          {},
          token
        ),
        api(
          `/api/market/quote/${encodeURIComponent(symbol)}`,
          {},
          token
        )
      ]);

      setData({
        ...h,
        quote: q
      });
    } catch (e:any) {
      Alert.alert('Market detail', e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    load();
  }, [symbol, range]);

  const loadAI = async () => {
    setAi(null);

    try {
      setAi(
        await api(
          `/api/ai/insight/${encodeURIComponent(symbol)}`,
          {},
          token
        )
      );
    } catch (e:any) {
      Alert.alert('AI insight', e.message);
    }
  };

  if (busy && !data) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color="#63dcb4" />
      </View>
    );
  }

  const q = data?.quote;

  return (
    <ScrollView contentContainerStyle={s.page}>
      <Pressable onPress={onBack}>
        <Text style={s.link}>‹ Back to markets</Text>
      </Pressable>

      <Text style={s.title}>{data?.name || symbol}</Text>
      <Text style={s.subtitle}>
        {symbol} · {data?.source || 'market data'}
      </Text>

      <View style={s.priceBox}>
        <Text style={s.bigPrice}>
          {q
            ? Number(q.price).toLocaleString('en-IN', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
              })
            : '—'}
        </Text>

        <Text style={q?.change_pct >= 0 ? s.up : s.down}>
          {q ? pct(q.change_pct) : '—'} (
          {q?.change >= 0 ? '+' : ''}
          {q?.change?.toFixed?.(2) ?? '—'})
        </Text>
      </View>

      <View style={s.rangeRow}>
        {['1d', '5d', '1m', '6m', '1y', '5y'].map(r => (
          <Pressable
            key={r}
            onPress={() => setRange(r)}
            style={range === r ? s.rangeActive : s.range}
          >
            <Text
              style={
                range === r
                  ? s.rangeTextActive
                  : s.rangeText
              }
            >
              {r.toUpperCase()}
            </Text>
          </Pressable>
        ))}
      </View>

      <CandlestickChart candles={data?.candles || []} />

      <View style={s.statsGrid}>
        {[
          ['Open', q?.open],
          ['High', q?.high],
          ['Low', q?.low],
          ['Prev close', q?.previous_close],
          ['Volume', q?.volume]
        ].map(([k, v]) => (
          <View key={String(k)} style={s.stat}>
            <Text style={s.muted}>{k}</Text>
            <Text style={s.statValue}>
              {typeof v === 'number'
                ? Number(v).toLocaleString('en-IN', {
                    maximumFractionDigits: 2
                  })
                : '—'}
            </Text>
          </View>
        ))}
      </View>

      <View style={s.aiCard}>
        <View style={s.aiHeader}>
          <Text style={s.section}>🤖 AI Intelligence</Text>

          <Pressable
            style={s.aiButton}
            onPress={loadAI}
          >
            <Text style={s.aiButtonText}>Analyze</Text>
          </Pressable>
        </View>

        {!ai ? (
          <Text style={s.muted}>
            Trend, volatility, indicators and ML diagnostics.
          </Text>
        ) : (
          <>
            <Text style={s.aiSignal}>{ai.signal}</Text>

            <Text style={s.muted}>
              Regime: {ai.regime} · Trend: {ai.trend} · Volatility:{' '}
              {ai.volatility}
            </Text>

            <Text style={s.aiMetric}>
              RSI {ai.rsi_14?.toFixed?.(1) ?? '—'} · MACD{' '}
              {ai.macd?.toFixed?.(2) ?? '—'}
            </Text>

            {ai.ml_research && (
              <Text style={s.muted}>
                ML research: {ai.ml_research.signal} · confidence{' '}
                {Number(ai.ml_research.confidence || 0).toFixed(0)}% ·{' '}
                {ai.ml_research.model_count} models
              </Text>
            )}

            {(ai.reasons || []).map((x:string, i:number) => (
              <Text key={i} style={s.reason}>
                • {x}
              </Text>
            ))}

            <Text style={s.disclaimer}>
              {ai.disclaimer}
            </Text>
          </>
        )}
      </View>
    </ScrollView>
  );
}

export default function App() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<'markets' | 'portfolio' | 'ai'>('markets');
  const [selected, setSelected] = useState<string | null>(null);

  const [portfolio, setPortfolio] = useState<any>(null);
  const [orders, setOrders] = useState<any[]>([]);
  const [symbol, setSymbol] = useState('RELIANCE.NS');
  const [qty, setQty] = useState('1');
  const [price, setPrice] = useState('1000');
  const [aiSymbol, setAiSymbol] = useState('^NSEI');
  const [ai, setAi] = useState<any>(null);

  const load = async (t = token) => {
    if (!t) return;

    try {
      setPortfolio(await api('/api/portfolio', {}, t));

      setOrders(
        (await api('/api/orders?limit=20', {}, t)).items || []
      );
    } catch (e:any) {
      Alert.alert('Unable to refresh', e.message);
    }
  };

  useEffect(() => {
    load();

    if (token) {
      const id = setInterval(() => load(), 5000);
      return () => clearInterval(id);
    }
  }, [token]);

  const auth = async () => {
    setBusy(true);

    try {
      const path =
        mode === 'login'
          ? '/api/auth/login'
          : '/api/auth/register';

      const j = await api(path, {
        method: 'POST',
        body: JSON.stringify({
          email,
          password
        })
      });

      setToken(j.access_token);
    } catch (e:any) {
      Alert.alert(
        mode === 'login'
          ? 'Login failed'
          : 'Registration failed',
        e.message
      );
    } finally {
      setBusy(false);
    }
  };

  const order = async (side:string) => {
    setBusy(true);

    try {
      await api(
        '/api/orders',
        {
          method: 'POST',
          headers: {
            'Idempotency-Key': `${Date.now()}-${side}`
          },
          body: JSON.stringify({
            symbol,
            side,
            quantity: Number(qty),
            price: Number(price)
          })
        },
        token!
      );

      await load();
    } catch (e:any) {
      Alert.alert('Order failed', e.message);
    } finally {
      setBusy(false);
    }
  };

  const deleteAccount = () =>
    Alert.alert(
      'Delete account',
      'This permanently deletes your paper portfolio, orders, positions and account. This cannot be undone.',
      [
        {
          text: 'Cancel',
          style: 'cancel'
        },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await api(
                '/api/account',
                {
                  method: 'DELETE'
                },
                token!
              );

              setToken(null);
            } catch (e:any) {
              Alert.alert('Deletion failed', e.message);
            }
          }
        }
      ]
    );

  const analyze = async () => {
    setBusy(true);

    try {
      setAi(
        await api(
          `/api/ai/insight/${encodeURIComponent(aiSymbol)}`,
          {},
          token!
        )
      );
    } catch (e:any) {
      Alert.alert('AI insight', e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <SafeAreaView style={s.root}>
        <StatusBar style="light" />

        <ScrollView contentContainerStyle={s.auth}>
          <Text style={s.title}>AI Trading Paper</Text>

          <Text style={s.subtitle}>
            Markets + AI research + paper trading
          </Text>

          <TextInput
            style={s.input}
            placeholder="Email"
            placeholderTextColor="#8d95a8"
            autoCapitalize="none"
            keyboardType="email-address"
            value={email}
            onChangeText={setEmail}
          />

          <TextInput
            style={s.input}
            placeholder="Password (8+ characters)"
            placeholderTextColor="#8d95a8"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />

          <Pressable
            style={s.primary}
            onPress={auth}
            disabled={busy}
          >
            {busy ? (
              <ActivityIndicator color="#07111d" />
            ) : (
              <Text style={s.primaryText}>
                {mode === 'login'
                  ? 'Sign in'
                  : 'Create account'}
              </Text>
            )}
          </Pressable>

          <Pressable
            onPress={() =>
              setMode(
                mode === 'login'
                  ? 'register'
                  : 'login'
              )
            }
          >
            <Text style={s.link}>
              {mode === 'login'
                ? 'New user? Create an account'
                : 'Already registered? Sign in'}
            </Text>
          </Pressable>

          <Text style={s.disclaimer}>
            Paper trading only. Market data and AI outputs are for
            research and may be delayed or unavailable.
          </Text>
        </ScrollView>
      </SafeAreaView>
    );
  }

  if (selected) {
    return (
      <SafeAreaView style={s.root}>
        <StatusBar style="light" />

        <DetailScreen
          token={token}
          symbol={selected}
          onBack={() => setSelected(null)}
        />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.root}>
      <StatusBar style="light" />

      {tab === 'markets' && (
        <MarketScreen
          token={token}
          onSelect={setSelected}
        />
      )}

      {tab === 'ai' && (
        <ScrollView contentContainerStyle={s.page}>
          <Text style={s.title}>AI Intelligence</Text>

          <Text style={s.subtitle}>
            Research signals, regime and ML diagnostics
          </Text>

          <TextInput
            style={s.input}
            value={aiSymbol}
            onChangeText={setAiSymbol}
            autoCapitalize="characters"
            placeholder="Symbol e.g. ^NSEI"
            placeholderTextColor="#77839a"
          />

          <Pressable
            style={s.primary}
            onPress={analyze}
            disabled={busy}
          >
            <Text style={s.primaryText}>
              {busy ? 'Analyzing…' : 'Analyze market'}
            </Text>
          </Pressable>

          {ai && (
            <View style={s.aiCard}>
              <Text style={s.aiSignal}>
                {ai.signal}
              </Text>

              <Text style={s.bigPrice}>
                {money(ai.price)}
              </Text>

              <Text style={s.subtitle}>
                {ai.name} · {ai.regime}
              </Text>

              <Text style={s.aiMetric}>
                RSI {ai.rsi_14?.toFixed?.(1) ?? '—'} ·
                MACD {ai.macd?.toFixed?.(2) ?? '—'} ·
                Trend {ai.trend}
              </Text>

              {ai.ml_research && (
                <Text style={s.muted}>
                  ML research: {ai.ml_research.signal} ·
                  confidence{' '}
                  {Number(
                    ai.ml_research.confidence || 0
                  ).toFixed(0)}%
                </Text>
              )}

              {(ai.reasons || []).map(
                (x:string, i:number) => (
                  <Text key={i} style={s.reason}>
                    • {x}
                  </Text>
                )
              )}

              <Text style={s.disclaimer}>
                {ai.disclaimer}
              </Text>
            </View>
          )}
        </ScrollView>
      )}

      {tab === 'portfolio' && (
        <ScrollView contentContainerStyle={s.page}>
          <View style={s.header}>
            <View>
              <Text style={s.title}>Portfolio</Text>
              <Text style={s.subtitle}>Paper trading</Text>
            </View>

            <Pressable onPress={() => setToken(null)}>
              <Text style={s.link}>Sign out</Text>
            </Pressable>
          </View>

          <View style={s.card}>
            <Text style={s.label}>Cash</Text>
            <Text style={s.value}>
              {money(portfolio?.cash)}
            </Text>

            <Text style={s.label}>Equity</Text>
            <Text style={s.value}>
              {money(portfolio?.equity)}
            </Text>
          </View>

          <Text style={s.section}>
            New paper order
          </Text>

          <TextInput
            style={s.input}
            value={symbol}
            onChangeText={setSymbol}
            autoCapitalize="characters"
          />

          <TextInput
            style={s.input}
            value={qty}
            onChangeText={setQty}
            keyboardType="decimal-pad"
          />

          <TextInput
            style={s.input}
            value={price}
            onChangeText={setPrice}
            keyboardType="decimal-pad"
          />

          <View style={s.row}>
            <Pressable
              style={s.primaryHalf}
              onPress={() => order('BUY')}
            >
              <Text style={s.primaryText}>
                BUY
              </Text>
            </Pressable>

            <Pressable
              style={s.secondaryHalf}
              onPress={() => order('SELL')}
            >
              <Text style={s.secondaryText}>
                SELL
              </Text>
            </Pressable>
          </View>

          <Text style={s.section}>
            Recent orders
          </Text>

          {orders.length === 0 ? (
            <Text style={s.muted}>
              No orders yet.
            </Text>
          ) : (
            orders.map(item => (
              <View
                key={String(item.id)}
                style={s.order}
              >
                <Text style={s.orderMain}>
                  {item.side} {item.quantity} {item.symbol}
                </Text>

                <Text style={s.muted}>
                  {money(item.price)} · {item.status}
                </Text>
              </View>
            ))
          )}

          <Pressable
            style={s.danger}
            onPress={deleteAccount}
          >
            <Text style={s.dangerText}>
              Delete account
            </Text>
          </Pressable>
        </ScrollView>
      )}

      <View style={s.nav}>
        {[
          ['markets', 'Markets', '⌂'],
          ['ai', 'AI', '✦'],
          ['portfolio', 'Portfolio', '◉']
        ].map(([k, label, icon]) => (
          <Pressable
            key={k}
            onPress={() => setTab(k as any)}
            style={
              tab === k
                ? s.navItemActive
                : s.navItem
            }
          >
            <Text
              style={
                tab === k
                  ? s.navIconActive
                  : s.navIcon
              }
            >
              {icon}
            </Text>

            <Text
              style={
                tab === k
                  ? s.navTextActive
                  : s.navText
              }
            >
              {label}
            </Text>
          </Pressable>
        ))}
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#07101f'
  },

  auth: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
    gap: 14
  },

  page: {
    padding: 20,
    paddingBottom: 105,
    gap: 12
  },

  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#07101f'
  },

  title: {
    fontSize: 30,
    fontWeight: '800',
    color: '#f4f7fb'
  },

  subtitle: {
    color: '#9aa6bb',
    marginTop: 4
  },

  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center'
  },

  input: {
    backgroundColor: '#111b2e',
    borderWidth: 1,
    borderColor: '#26334d',
    borderRadius: 14,
    padding: 15,
    color: '#f4f7fb',
    fontSize: 16
  },

  primary: {
    backgroundColor: '#63dcb4',
    padding: 15,
    borderRadius: 14,
    alignItems: 'center'
  },

  primaryText: {
    color: '#07111d',
    fontWeight: '800'
  },

  link: {
    color: '#63dcb4',
    fontWeight: '700',
    paddingVertical: 8
  },

  disclaimer: {
    color: '#77839a',
    fontSize: 11,
    lineHeight: 17,
    marginTop: 10
  },

  card: {
    backgroundColor: '#101a2c',
    borderRadius: 18,
    padding: 18,
    borderWidth: 1,
    borderColor: '#202d45'
  },

  label: {
    color: '#8f9bb0',
    fontSize: 12,
    marginTop: 5
  },

  value: {
    color: '#f4f7fb',
    fontSize: 25,
    fontWeight: '800',
    marginBottom: 8
  },

  section: {
    color: '#f4f7fb',
    fontSize: 19,
    fontWeight: '800',
    marginTop: 8
  },

  row: {
    flexDirection: 'row',
    gap: 10
  },

  primaryHalf: {
    flex: 1,
    backgroundColor: '#63dcb4',
    padding: 15,
    borderRadius: 14,
    alignItems: 'center'
  },

  secondaryHalf: {
    flex: 1,
    backgroundColor: '#17243a',
    padding: 15,
    borderRadius: 14,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#2c3b57'
  },

  secondaryText: {
    color: '#f4f7fb',
    fontWeight: '800'
  },

  order: {
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1c2940'
  },

  orderMain: {
    color: '#f4f7fb',
    fontWeight: '700'
  },

  muted: {
    color: '#7f8ba0'
  },

  danger: {
    marginTop: 25,
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#743f4b',
    alignItems: 'center'
  },

  dangerText: {
    color: '#ff8c9b',
    fontWeight: '700'
  },

  live: {
    color: '#63dcb4',
    fontWeight: '800',
    fontSize: 12
  },

  marketHero: {
    backgroundColor: '#101a2c',
    padding: 16,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#202d45'
  },

  heroTitle: {
    color: '#f4f7fb',
    fontSize: 18,
    fontWeight: '800'
  },

  heroText: {
    color: '#8f9bb0',
    marginTop: 5,
    lineHeight: 19
  },

  marketRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1c2940'
  },

  marketName: {
    color: '#f4f7fb',
    fontWeight: '700',
    fontSize: 16
  },

  marketPrice: {
    color: '#f4f7fb',
    fontWeight: '700',
    fontSize: 16
  },

  up: {
    color: '#63dcb4',
    fontWeight: '700'
  },

  down: {
    color: '#ff7182',
    fontWeight: '700'
  },

  priceBox: {
    marginTop: 8,
    marginBottom: 5
  },

  bigPrice: {
    color: '#f4f7fb',
    fontSize: 34,
    fontWeight: '800'
  },

  rangeRow: {
    flexDirection: 'row',
    gap: 7,
    marginVertical: 8
  },

  range: {
    paddingVertical: 9,
    paddingHorizontal: 12,
    borderRadius: 12
  },

  rangeActive: {
    paddingVertical: 9,
    paddingHorizontal: 12,
    borderRadius: 12,
    backgroundColor: '#1a2942'
  },

  rangeText: {
    color: '#8f9bb0',
    fontWeight: '700',
    fontSize: 12
  },

  rangeTextActive: {
    color: '#f4f7fb',
    fontWeight: '800',
    fontSize: 12
  },

  chart: {
    height: 220,
    backgroundColor: '#0c1627',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#202d45',
    overflow: 'hidden'
  },

  chartEmpty: {
    height: 220,
    justifyContent: 'center',
    alignItems: 'center'
  },

  chartHigh: {
    position: 'absolute',
    right: 7,
    top: 5,
    color: '#77839a',
    fontSize: 10
  },

  chartLow: {
    position: 'absolute',
    right: 7,
    bottom: 5,
    color: '#77839a',
    fontSize: 10
  },

  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    backgroundColor: '#101a2c',
    borderRadius: 16,
    padding: 12
  },

  stat: {
    width: '50%',
    padding: 8
  },

  statValue: {
    color: '#f4f7fb',
    fontWeight: '700',
    marginTop: 3
  },

  aiCard: {
    backgroundColor: '#101a2c',
    borderRadius: 18,
    padding: 17,
    borderWidth: 1,
    borderColor: '#26334d',
    gap: 7
  },

  aiHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center'
  },

  aiButton: {
    backgroundColor: '#1c2d47',
    paddingVertical: 8,
    paddingHorizontal: 13,
    borderRadius: 10
  },

  aiButtonText: {
    color: '#63dcb4',
    fontWeight: '800'
  },

  aiSignal: {
    color: '#63dcb4',
    fontSize: 24,
    fontWeight: '800'
  },

  aiMetric: {
    color: '#f4f7fb',
    fontWeight: '700',
    marginTop: 5
  },

  reason: {
    color: '#b7c0d0',
    lineHeight: 20
  },

  nav: {
    position: 'absolute',
    left: 12,
    right: 12,
    bottom: 10,
    height: 68,
    borderRadius: 22,
    backgroundColor: '#121d31',
    borderWidth: 1,
    borderColor: '#26334d',
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center'
  },

  navItem: {
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 80
  },

  navItemActive: {
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 80,
    backgroundColor: '#1b2b47',
    paddingVertical: 7,
    paddingHorizontal: 13,
    borderRadius: 16
  },

  navIcon: {
    color: '#7f8ba0',
    fontSize: 20
  },

  navIconActive: {
    color: '#8fb8ff',
    fontSize: 20
  },

  navText: {
    color: '#7f8ba0',
    fontSize: 11,
    marginTop: 2
  },

  navTextActive: {
    color: '#9ab8ff',
    fontSize: 11,
    fontWeight: '800',
    marginTop: 2
  }
});

