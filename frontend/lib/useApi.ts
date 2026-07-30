"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";
import { apiFetch } from "./api";

/**
 * Client-component hook: returns a fetch function pre-wired with the
 * current Clerk session token. useAuth().getToken() is itself already
 * cached/memoized by Clerk's SDK, so we don't need to worry about this
 * re-fetching a token on every keystroke — but we do re-fetch a fresh
 * token on every call rather than caching it ourselves, since Clerk
 * tokens are short-lived and a stale cached token would cause confusing
 * intermittent 401s.
 */
export function useApi() {
  const { getToken } = useAuth();

  const call = useCallback(
    async <T,>(path: string, options: Parameters<typeof apiFetch>[1] = {}) => {
      const token = await getToken();
      return apiFetch<T>(path, { ...options, token });
    },
    [getToken]
  );

  return { call };
}
