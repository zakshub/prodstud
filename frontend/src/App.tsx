import React, { useEffect, useState } from "react";
import { api } from "./api/client";
import type {
  ProductionTemplateRecord,
  ProjectRecord,
  ProviderModelCapability,
  UserProfile,
} from "./api/types";
import { AuthView } from "./views/AuthView";
import { LibraryCompareView } from "./views/LibraryCompareView";
import { ProjectsView } from "./views/ProjectsView";
import { ProtocolsView } from "./views/ProtocolsView";
import { SettingsView } from "./views/SettingsView";
import { WorkspaceView } from "./views/WorkspaceView";

type ActiveTab = "projects" | "workspace" | "library" | "protocols" | "settings";

export const App: React.FC = () => {
  const [booting, setBooting] = useState(true);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [storageBytes, setStorageBytes] = useState(0);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  const [activeTab, setActiveTab] = useState<ActiveTab>("projects");
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [activeProjectId, setActiveProjectId] = useState<string>("");
  const [capabilities, setCapabilities] = useState<ProviderModelCapability[]>([]);
  const [templates, setTemplates] = useState<ProductionTemplateRecord[]>([]);
  const [comparePair, setComparePair] = useState<[string, string] | null>(null);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const loadAuthedState = async (showArchived = includeArchived) => {
    const sess = await api.session();
    if (!sess.authenticated || !sess.user) {
      setUser(null);
      return;
    }
    const [prjList, caps, tpls] = await Promise.all([
      api.listProjects(showArchived),
      api.listCapabilities(),
      api.listTemplates(),
    ]);
    setUser(sess.user);
    setStorageBytes(sess.storage_usage_bytes ?? 0);
    setTheme(sess.user.preferred_theme === "light" ? "light" : "dark");
    setProjects(prjList);
    setCapabilities(caps);
    setTemplates(tpls);
    if (!activeProjectId && prjList.length > 0) {
      setActiveProjectId(prjList[0].id);
    }
  };

  useEffect(() => {
    loadAuthedState(false)
      .catch(() => setUser(null))
      .finally(() => setBooting(false));
  }, []);

  const handleToggleTheme = async () => {
    const next: "dark" | "light" = theme === "dark" ? "light" : "dark";
    setTheme(next);
    if (user) {
      try {
        const updated = await api.updateSettings({ preferred_theme: next });
        setUser(updated);
      } catch {
        /* non-blocking */
      }
    }
  };

  const handleAuthenticated = async (authedUser: UserProfile) => {
    setUser(authedUser);
    await loadAuthedState(false);
    setActiveTab("projects");
  };

  const handleLogout = async () => {
    await api.logout();
    setUser(null);
    setProjects([]);
    setActiveProjectId("");
  };

  if (booting) {
    return (
      <main className="auth-shell">
        <div className="panel">Initializing Production Studio...</div>
      </main>
    );
  }

  if (!user) {
    return <AuthView theme={theme} onToggleTheme={handleToggleTheme} onAuthenticated={handleAuthenticated} />;
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-left">
          <div className="brand-mark">
            <span className="brand-dot" aria-hidden="true" />
            <span>Production Studio</span>
          </div>
          <nav className="nav-tabs" aria-label="Primary Workspace Navigation">
            <button
              type="button"
              className="nav-tab"
              aria-current={activeTab === "projects" ? "page" : undefined}
              onClick={() => setActiveTab("projects")}
            >
              Projects
            </button>
            <button
              type="button"
              className="nav-tab"
              aria-current={activeTab === "workspace" ? "page" : undefined}
              disabled={!activeProjectId}
              onClick={() => setActiveTab("workspace")}
            >
              Workspace
            </button>
            <button
              type="button"
              className="nav-tab"
              aria-current={activeTab === "library" ? "page" : undefined}
              onClick={() => {
                setComparePair(null);
                setActiveTab("library");
              }}
            >
              Assets &amp; Compare
            </button>
            <button
              type="button"
              className="nav-tab"
              aria-current={activeTab === "protocols" ? "page" : undefined}
              onClick={() => setActiveTab("protocols")}
            >
              170 Protocols
            </button>
            <button
              type="button"
              className="nav-tab"
              aria-current={activeTab === "settings" ? "page" : undefined}
              onClick={() => setActiveTab("settings")}
            >
              Settings
            </button>
          </nav>
        </div>

        <div className="topbar-right">
          <span className="spend-pill" title="Daily Spend Guard (Today / Limit)">
            Spend ${user.spent_today_usd.toFixed(2)} / ${user.daily_spend_cap_usd.toFixed(2)}
          </span>
          <button id="theme-toggle-btn" type="button" className="btn btn-sm" onClick={handleToggleTheme}>
            {theme === "dark" ? "Light Mode" : "Dark Mode"}
          </button>
          <button type="button" className="btn btn-sm" onClick={handleLogout}>
            Sign Out
          </button>
        </div>
      </header>

      {activeTab === "projects" && (
        <ProjectsView
          projects={projects}
          templates={templates}
          includeArchived={includeArchived}
          onToggleArchived={async (v) => {
            setIncludeArchived(v);
            setProjects(await api.listProjects(v));
          }}
          onOpenProject={(pid) => {
            setActiveProjectId(pid);
            setActiveTab("workspace");
          }}
          onProjectsChanged={async () => {
            await loadAuthedState(includeArchived);
          }}
        />
      )}

      {activeTab === "workspace" && activeProjectId && (
        <WorkspaceView
          projects={projects}
          activeProjectId={activeProjectId}
          capabilities={capabilities}
          templates={templates}
          onSelectProject={(pid) => setActiveProjectId(pid)}
          onRefreshGlobal={() => loadAuthedState(includeArchived)}
          onOpenCompare={(l, r) => {
            setComparePair([l, r]);
            setActiveTab("library");
          }}
        />
      )}

      {activeTab === "library" && (
        <LibraryCompareView
          storageUsageBytes={storageBytes}
          initialComparePair={comparePair}
          onOpenProjectAsset={(pid) => {
            setActiveProjectId(pid);
            setActiveTab("workspace");
          }}
        />
      )}

      {activeTab === "protocols" && <ProtocolsView />}

      {activeTab === "settings" && (
        <SettingsView
          user={user}
          capabilities={capabilities}
          theme={theme}
          onToggleTheme={handleToggleTheme}
          onUserUpdated={setUser}
        />
      )}
    </div>
  );
};
