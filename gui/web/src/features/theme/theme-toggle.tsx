import { Moon, Sun } from "lucide-react";

import { useTheme } from "../../app/providers/theme-context";
import { Button } from "../../components/ui/button";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const nextTheme = theme === "dark" ? "light" : "dark";
  const Icon = theme === "dark" ? Sun : Moon;

  return (
    <Button
      aria-label={`Switch to ${nextTheme} theme`}
      onClick={toggleTheme}
      size="icon"
      title={`Switch to ${nextTheme} theme`}
      type="button"
      variant="ghost"
    >
      <Icon aria-hidden="true" className="size-3.5" strokeWidth={1.8} />
    </Button>
  );
}
