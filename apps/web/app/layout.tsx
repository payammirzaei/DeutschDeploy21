import type { Metadata, Viewport } from "next";

import { OfflineAttemptSync } from "@/src/components/offline-attempt-sync";
import { ServiceWorkerRegistration } from "@/src/components/service-worker-registration";

import "./globals.css";
import styles from "./layout.module.css";

export const metadata: Metadata = {
  title: {
    default: "DeutschDeploy21",
    template: "%s · DeutschDeploy21",
  },
  description: "Speak German. Explain your work. Get hired.",
  applicationName: "DeutschDeploy21",
};

export const viewport: Viewport = {
  themeColor: "#f4efe4",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className={styles.skipLink} href="#main-content">
          Skip to main content
        </a>
        <ServiceWorkerRegistration />
        <OfflineAttemptSync />
        <div id="main-content" tabIndex={-1}>
          {children}
        </div>
      </body>
    </html>
  );
}
