/**
 * Voco V2 Licensing — Keygen.sh integration for license validation
 * and tier-gated update channels.
 *
 * Architecture: The frontend validates the license key via Keygen's
 * public API. The license tier determines which CrabNebula release
 * channel the user can access for updates.
 *
 * Tier → Channel mapping:
 *   listener    → stable only
 *   orchestrator → stable + beta
 *   architect   → stable + beta + nightly (early access)
 */

import { invoke } from "@tauri-apps/api/core";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const KEYGEN_ACCOUNT_ID = import.meta.env.VITE_KEYGEN_ACCOUNT_ID ?? "";
const KEYGEN_API_BASE = `https://api.keygen.sh/v1/accounts/${KEYGEN_ACCOUNT_ID}`;

export type LicenseTier = "listener" | "orchestrator" | "architect";

export type UpdateChannel = "stable" | "beta" | "nightly";

// ---------------------------------------------------------------------------
// Tier → Channel mapping
// ---------------------------------------------------------------------------

const TIER_CHANNELS: Record<LicenseTier, UpdateChannel[]> = {
  listener: ["stable"],
  orchestrator: ["stable", "beta"],
  architect: ["stable", "beta", "nightly"],
};

export function getChannelsForTier(tier: LicenseTier): UpdateChannel[] {
  return TIER_CHANNELS[tier] ?? TIER_CHANNELS.listener;
}

export function getHighestChannel(tier: LicenseTier): UpdateChannel {
  const channels = getChannelsForTier(tier);
  return channels[channels.length - 1];
}

// ---------------------------------------------------------------------------
// License validation response
// ---------------------------------------------------------------------------

export interface LicenseValidation {
  valid: boolean;
  tier: LicenseTier;
  channel: UpdateChannel;
  expiresAt: string | null;
  metadata: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Validate a license key against Keygen's API
// ---------------------------------------------------------------------------

export async function validateLicenseKey(
  licenseKey: string,
): Promise<LicenseValidation> {
  if (!KEYGEN_ACCOUNT_ID) {
    console.warn("[licensing] KEYGEN_ACCOUNT_ID not set, defaulting to listener");
    return {
      valid: false,
      tier: "listener",
      channel: "stable",
      expiresAt: null,
      metadata: {},
    };
  }

  try {
    const resp = await fetch(`${KEYGEN_API_BASE}/licenses/actions/validate-key`, {
      method: "POST",
      headers: { "Content-Type": "application/vnd.api+json", Accept: "application/vnd.api+json" },
      body: JSON.stringify({
        meta: { key: licenseKey },
      }),
    });

    if (!resp.ok) {
      return {
        valid: false,
        tier: "listener",
        channel: "stable",
        expiresAt: null,
        metadata: { error: `HTTP ${resp.status}` },
      };
    }

    const data = await resp.json();
    const meta = data.meta;
    const attrs = data.data?.attributes ?? {};
    const policyName = data.data?.relationships?.policy?.data?.id ?? "";

    const tier = resolveTierFromPolicy(policyName, attrs.metadata);
    const valid = meta?.valid === true;

    return {
      valid,
      tier,
      channel: getHighestChannel(tier),
      expiresAt: attrs.expiry ?? null,
      metadata: attrs.metadata ?? {},
    };
  } catch (err) {
    console.error("[licensing] validation failed:", err);
    return {
      valid: false,
      tier: "listener",
      channel: "stable",
      expiresAt: null,
      metadata: { error: err instanceof Error ? err.message : String(err) },
    };
  }
}

// ---------------------------------------------------------------------------
// Resolve tier from Keygen policy
// ---------------------------------------------------------------------------

function resolveTierFromPolicy(
  policyId: string,
  metadata?: Record<string, unknown>,
): LicenseTier {
  const tierHint = metadata?.tier as string | undefined;
  if (tierHint === "architect" || tierHint === "orchestrator" || tierHint === "listener") {
    return tierHint;
  }

  const lower = policyId.toLowerCase();
  if (lower.includes("architect")) return "architect";
  if (lower.includes("orchestrator")) return "orchestrator";
  return "listener";
}

// ---------------------------------------------------------------------------
// Persist / Load license key via Tauri secure storage
// ---------------------------------------------------------------------------

const LICENSE_KEY_STORAGE = "voco-license-key";

export async function saveLicenseKey(key: string): Promise<void> {
  try {
    await invoke("save_api_keys", {
      keys: { [LICENSE_KEY_STORAGE]: key },
    });
  } catch {
    localStorage.setItem(LICENSE_KEY_STORAGE, key);
  }
}

export async function loadLicenseKey(): Promise<string | null> {
  try {
    const keys = await invoke<Record<string, string>>("load_api_keys");
    return keys[LICENSE_KEY_STORAGE] ?? null;
  } catch {
    return localStorage.getItem(LICENSE_KEY_STORAGE);
  }
}
