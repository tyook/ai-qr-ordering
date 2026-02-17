"use client";

import { useEffect } from "react";

export function AppleAuthInit() {
  useEffect(() => {
    const AppleID = (window as unknown as Record<string, unknown>).AppleID as
      | { auth: { init: (config: Record<string, unknown>) => void } }
      | undefined;
    if (AppleID) {
      AppleID.auth.init({
        clientId: process.env.NEXT_PUBLIC_APPLE_CLIENT_ID || "",
        scope: "name email",
        redirectURI: window.location.origin,
        usePopup: true,
      });
    }
  }, []);

  return null;
}
