import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "DeutschDeploy21",
    short_name: "DD21",
    description: "21 focused days to stronger German software interviews.",
    start_url: "/",
    display: "standalone",
    background_color: "#f6f8fb",
    theme_color: "#f6f8fb",
    orientation: "portrait-primary",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
