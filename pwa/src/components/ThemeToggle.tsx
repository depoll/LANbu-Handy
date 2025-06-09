import { useTheme } from '../hooks/useTheme';
import { type Theme } from '../types/theme';

export function ThemeToggle() {
  const { theme, actualTheme, setTheme } = useTheme();

  const getThemeIcon = (themeType: Theme) => {
    switch (themeType) {
      case 'light':
        return '☀️';
      case 'dark':
        return '🌙';
      case 'system':
        return '🌓';
      default:
        return '🌓';
    }
  };

  const getThemeLabel = (themeType: Theme) => {
    switch (themeType) {
      case 'light':
        return 'Light theme';
      case 'dark':
        return 'Dark theme';
      case 'system':
        return `Auto theme (${actualTheme})`;
      default:
        return 'Auto theme';
    }
  };

  const themes: Theme[] = ['light', 'dark', 'system'];

  return (
    <div className="theme-toggle-compact">
      <div className="theme-toggle-buttons-compact">
        {themes.map(themeOption => (
          <button
            key={themeOption}
            type="button"
            className={`theme-toggle-button-compact ${theme === themeOption ? 'active' : ''}`}
            onClick={() => setTheme(themeOption)}
            aria-label={getThemeLabel(themeOption)}
            title={getThemeLabel(themeOption)}
          >
            <span className="theme-icon-compact" aria-hidden="true">
              {getThemeIcon(themeOption)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
