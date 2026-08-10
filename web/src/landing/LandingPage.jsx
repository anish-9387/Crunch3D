import Layout from './Layout'
import HeroSection from './components/HeroSection'
import FeatureCards from './components/FeatureCards'
import UseCasesSection from './components/UseCasesSection'
import AboutSection from './components/AboutSection'
import SupportedPlatforms from './components/SupportedPlatforms'

export default function LandingPage({ onTryDemo, onGenerateLods }) {
  return (
    <Layout onTryDemo={onTryDemo}>
      <HeroSection onTryDemo={onTryDemo} />
      <FeatureCards />
      <UseCasesSection />
      <AboutSection onGenerateLods={onGenerateLods} />
      <SupportedPlatforms />
    </Layout>
  )
}
