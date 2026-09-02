import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "DeutschDeploy21",
    short_name: "DD21",
    description: "21 focused days to stronger German software interviews.",
    start_url: "/",
    display: "standalone",
    background_color: "#f4efe4",
    theme_color: "#f4efe4",
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
