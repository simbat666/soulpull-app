import './App.css'
import { useEffect, useMemo, useState } from 'react'
import { TonConnectButton, useTonConnectUI, useTonWallet } from '@tonconnect/ui-react'

type TonProofPayloadResponse = {
  payload: string
  ttlSeconds: number
  issuedAt: number
}

type TonProofVerifyRequest = {
  address: string
  publicKey?: string
  walletStateInit: string
  proof: {
    timestamp: number
    domain: {
      lengthBytes: number
      value: string
    }
    payload: string
    signature: string
  }
}

type TonProofVerifyResponse =
  | { ok: true; address: string }
  | { ok: false; error: string; expected?: string; got?: string }

function App() {
  const wallet = useTonWallet()
  const [tonConnectUI] = useTonConnectUI()

  const [proofStatus, setProofStatus] = useState<
    'idle' | 'loading_payload' | 'ready' | 'verifying' | 'ok' | 'error'
  >('idle')
  const [proofError, setProofError] = useState<string | null>(null)

  const connectedAddress = wallet?.account?.address ?? null
  const connectedPublicKey = wallet?.account?.publicKey ?? null
  const walletStateInit = wallet?.account?.walletStateInit ?? null

  const tonProof = useMemo(() => {
    const item = wallet?.connectItems?.tonProof
    if (!item || !('proof' in item)) return null
    return item.proof
  }, [wallet])

  // Fetch a fresh ton_proof payload and attach it to connect request
  useEffect(() => {
    let cancelled = false

    async function run() {
      try {
        setProofStatus('loading_payload')
        setProofError(null)

        tonConnectUI.setConnectRequestParameters({ state: 'loading' })

        const res = await fetch('/api/v1/ton-proof/payload', {
          method: 'GET',
          credentials: 'include',
        })
        if (!res.ok) throw new Error(`payload request failed: ${res.status}`)
        const data = (await res.json()) as TonProofPayloadResponse

        if (cancelled) return

        tonConnectUI.setConnectRequestParameters({
          state: 'ready',
          value: { tonProof: data.payload },
        })
        setProofStatus('ready')
      } catch (e) {
        tonConnectUI.setConnectRequestParameters(null)
        setProofStatus('error')
        setProofError(e instanceof Error ? e.message : 'payload error')
      }
    }

    void run()
    return () => {
      cancelled = true
    }
  }, [tonConnectUI])

  // When proof arrives from wallet, send it to backend for verification
  useEffect(() => {
    let cancelled = false

    async function verify() {
      if (!wallet || !tonProof || !connectedAddress || !walletStateInit) return

      setProofStatus('verifying')
      setProofError(null)

      const req: TonProofVerifyRequest = {
        address: connectedAddress,
        publicKey: connectedPublicKey ?? undefined,
        walletStateInit,
        proof: tonProof,
      }

      const res = await fetch('/api/v1/ton-proof/verify', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
      })

      const data = (await res.json()) as TonProofVerifyResponse
      if (cancelled) return

      if (res.ok && data.ok) {
        setProofStatus('ok')
        setProofError(null)
      } else {
        setProofStatus('error')
        setProofError((data as any).error ?? `verify failed: ${res.status}`)
      }
    }

    void verify()
    return () => {
      cancelled = true
    }
  }, [wallet, tonProof, connectedAddress, connectedPublicKey, walletStateInit])

  return (
    <div className="page">
      <header className="header">
        <div className="brand">Soulpull</div>
        <TonConnectButton />
      </header>

      <main className="main">
        <h1>TON Connect</h1>

        <section className="card">
          <div className="row">
            <div className="label">Status</div>
            <div className="value">{proofStatus}</div>
          </div>

          <div className="row">
            <div className="label">Wallet</div>
            <div className="value mono">{connectedAddress ?? 'not connected'}</div>
          </div>

          <div className="row">
            <div className="label">Public key</div>
            <div className="value mono">{connectedPublicKey ?? '—'}</div>
          </div>

          {proofError ? (
            <div className="error mono">{proofError}</div>
          ) : (
            <div className="hint">
              Connect wallet — backend will verify <code>ton_proof</code> and create a session.
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

export default App
