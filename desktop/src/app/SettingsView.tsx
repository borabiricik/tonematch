import * as React from "react";
import * as cli from "../cli";
import { Button, Card, Kbd, Notice, Segmented, Switch } from "../ds";
import { kbd, LIBRARY_KEY, save, type Theme } from "./state";

// Per-machine preferences (localStorage), demo mode, where the engine lives, and the keyboard map.

type Props = { theme: Theme; setTheme: (t: Theme) => void; env: cli.EnvInfo | null };

const SHORTCUTS: [string, string][] = [
  [kbd("1"), "Ton çıkar"], [kbd("2"), "Kütüphane"], [kbd("3"), "Cihaz"], [kbd("4"), "Tuner"], [kbd(","), "Ayarlar"],
  [kbd("K"), "Yeni ton: şarkı alanına git"], ["/", "Ton çıkar'da şarkı alanına git"], [kbd("↵"), "Tonu çıkar"],
  [kbd("J"), "Çıktıyı aç / kapat"], ["Space", "Tuner'ı aç / kapat · kalibrasyonda kaydı başlat"], ["Esc", "Pencereyi kapat"],
];

export function SettingsView({ theme, setTheme, env }: Props) {
  const [cleared, setCleared] = React.useState(false);
  return (
    <section className="page settings">
      <header className="page__head">
        <div>
          <h1 className="t-title">Ayarlar</h1>
          <p className="t-small page__sub">Bu ayarlar sadece bu bilgisayarda saklanır.</p>
        </div>
      </header>

      <div className="settings__grid">
        <Card>
          <h2 className="t-heading settings__h">Görünüm</h2>
          <Segmented<Theme> name="theme" label="Tema" value={theme} onChange={setTheme}
            hint="Sahne koyu, gündüz açık. Sistem, bilgisayarın ayarını izler."
            options={[{ value: "system", label: "Sistem", icon: "auto" }, { value: "dark", label: "Sahne", icon: "moon" }, { value: "light", label: "Gündüz", icon: "sun" }]} />
        </Card>

        <Card>
          <h2 className="t-heading settings__h">Demo modu</h2>
          {cli.IN_TAURI ? (
            <Switch checked={cli.DEMO} onChange={cli.setDemo} label="Cihaz olmadan dene"
              hint="Açıkken hiçbir komut çalışmaz: slotlar, ton çıkarma, tuner ve kalibrasyon örnek veriyle canlandırılır. Değiştirince uygulama yeniden yüklenir." />
          ) : (
            <Notice tone="warn" title="Tarayıcıda çalışıyor">Tauri olmadan motor çalışamaz; demo modu hep açık.</Notice>
          )}
        </Card>

        <Card>
          <h2 className="t-heading settings__h">Motor</h2>
          {env ? (
            <dl className="settings__env">
              <div><dt>Durum</dt><dd>{env.ready ? "Hazır" : "Bulunamadı: uv sync gerekli (docs/09-setup.md)"}</dd></div>
              <div><dt>Proje</dt><dd className="t-console">{env.project}</dd></div>
              <div><dt>Python ortamı</dt><dd className="t-console">{env.venv}</dd></div>
              <div><dt>uv</dt><dd className="t-console">{env.uv ?? "—"}</dd></div>
              <div><dt>Platform</dt><dd>{env.platform}</dd></div>
            </dl>
          ) : <p className="t-small">Okunuyor…</p>}
        </Card>

        <Card>
          <h2 className="t-heading settings__h">Kütüphane</h2>
          <p className="t-small settings__p">Çıkardığın tonların listesi. Silmek cihazı, .tsl dosyalarını ve yedekleri etkilemez.</p>
          <Button variant="danger" size="sm" disabled={cleared} onClick={() => { save(LIBRARY_KEY, []); setCleared(true); }}>
            {cleared ? "Temizlendi" : "Listeyi temizle"}
          </Button>
        </Card>

        <Card className="settings__wide">
          <h2 className="t-heading settings__h">Klavye kısayolları</h2>
          <dl className="shortcuts">
            {SHORTCUTS.map(([k, what]) => <div key={what}><dt><Kbd>{k}</Kbd></dt><dd>{what}</dd></div>)}
          </dl>
        </Card>
      </div>

      <p className="t-small settings__legal">
        ToneMatch 0.1 · BOSS, GT-1 ve BOSS TONE STUDIO, Roland Corporation'ın ticari markalarıdır. Bu proje Roland/BOSS ile bağlantılı değildir.
      </p>
    </section>
  );
}
