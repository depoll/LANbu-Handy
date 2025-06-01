# LANbu Handy PWA

Progressive Web Application for slicing and printing 3D models to Bambu Lab printers in LAN-only mode.

## Technology Stack

- **Frontend**: React 19 with TypeScript
- **Build Tool**: Vite
- **Styling**: CSS3 with mobile-first responsive design

## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Lint code
npm run lint

# Preview production build
npm run preview
```

## Features

- 🔗 **URL to Print**: Provide a URL to your 3D model and start printing
- ⚙️ **Local Slicing**: Uses embedded Bambu Studio CLI for reliable slicing
- 🏠 **LAN Only**: Operates entirely within your local network

## Project Structure

```
src/
├── components/          # React components
│   ├── Header.tsx       # App header
│   ├── Hero.tsx         # Hero section
│   ├── Features.tsx     # Feature cards
│   └── Footer.tsx       # App footer
├── App.tsx              # Main app component
├── App.css              # App-specific styles
├── main.tsx             # React entry point
└── index.css            # Global styles
```

This is Phase 0 of the LANbu Handy project - establishing the basic PWA structure and foundation for future development phases.