import PrinterSelector from './PrinterSelector';

function Header() {
  return (
    <header>
      <div className="header-content">
        <h1>LANbu Handy PWA</h1>
        <p>Self-hosted 3D printing for Bambu Lab printers</p>
      </div>
      <PrinterSelector className="header-printer-selector" />
    </header>
  );
}

export default Header;
