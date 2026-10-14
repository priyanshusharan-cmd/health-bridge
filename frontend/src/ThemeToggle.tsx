import { useText } from "./locale";
import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle() {
  const tr = useText();

  const [theme, setTheme] = useState<"light" | "dark">(() =>
    document.documentElement.dataset.theme === "dark" ? "dark" : "light",
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    try {
      localStorage.setItem("healthbridge-theme", theme);
    } catch {
      /* Storage may be disabled. */
    }
  }, [theme]);
  const next = theme === "light" ? "dark" : "light";
  return (
    <button
      className="theme-toggle"
      onClick={() => setTheme(next)}
      aria-label={tr(`Switch to ${next} mode`)}
      title={tr(`Switch to ${next} mode`)}
    >
      {theme === "light" ? <Moon size={17} /> : <Sun size={17} />}
      <span>{tr(theme === "light" ? "Dark" : "Light")}</span>
    </button>
  );
}
