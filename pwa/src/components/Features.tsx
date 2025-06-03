interface FeatureCardProps {
  title: string;
  description: string;
  icon: string;
  onClick: () => void;
}

function FeatureCard({ title, description, icon, onClick }: FeatureCardProps) {
  return (
    <div className="feature-card" onClick={onClick}>
      <h3>
        {icon} {title}
      </h3>
      <p>{description}</p>
    </div>
  );
}

interface FeaturesProps {
  onFeatureClick: (featureName: string) => void;
}

function Features({ onFeatureClick }: FeaturesProps) {
  const features = [
    {
      title: 'URL to Print',
      icon: '🔗',
      description: 'Provide a URL to your 3D model and start printing',
    },
    {
      title: 'Local Slicing',
      icon: '⚙️',
      description: 'Uses embedded Bambu Studio CLI for reliable slicing',
    },
    {
      title: 'LAN Only',
      icon: '🏠',
      description: 'Operates entirely within your local network',
    },
  ];

  return (
    <section className="features">
      {features.map((feature, index) => (
        <FeatureCard
          key={index}
          title={feature.title}
          icon={feature.icon}
          description={feature.description}
          onClick={() => onFeatureClick(feature.title)}
        />
      ))}
    </section>
  );
}

export default Features;
