"use client";

import Image from "next/image";
import { useEffect, useRef, useState, useCallback } from "react";
import { Sprout, Cloud, Bug, Droplets, Calendar, FileText } from "lucide-react";

const features = [
  {
    icon: Sprout,
    title: "Crop Management",
    description: "Get personalized advice for planting, growing, and harvesting your crops based on local conditions.",
  },
  {
    icon: Bug,
    title: "Pest Control",
    description: "Identify pests and diseases instantly. Receive organic and chemical treatment recommendations.",
  },
  {
    icon: Cloud,
    title: "Weather Insights",
    description: "Real-time weather forecasts and alerts tailored to your farm location and crop needs.",
  },
  {
    icon: Droplets,
    title: "Irrigation Guide",
    description: "Smart water management tips based on soil type, weather, and crop requirements.",
  },
  {
    icon: Calendar,
    title: "Harvest Planning",
    description: "Optimal harvest timing predictions to maximize yield and quality of your produce.",
  },
  {
    icon: FileText,
    title: "Government Schemes",
    description: "Stay updated on agricultural subsidies, loans, and government programs you qualify for.",
  },
];

export function PhilosophySection() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const [leftTranslateX, setLeftTranslateX] = useState(-100);
  const [rightTranslateX, setRightTranslateX] = useState(100);
  const [titleOpacity, setTitleOpacity] = useState(1);
  const rafRef = useRef<number | null>(null);

  const updateTransforms = useCallback(() => {
    if (!sectionRef.current) return;
    
    const rect = sectionRef.current.getBoundingClientRect();
    const windowHeight = window.innerHeight;
    const sectionHeight = sectionRef.current.offsetHeight;
    
    // Calculate progress based on scroll position
    const scrollableRange = sectionHeight - windowHeight;
    const scrolled = -rect.top;
    const progress = Math.max(0, Math.min(1, scrolled / scrollableRange));
    
    // Left comes from left (-100% to 0%)
    setLeftTranslateX((1 - progress) * -100);
    
    // Right comes from right (100% to 0%)
    setRightTranslateX((1 - progress) * 100);
    
    // Title fades out as blocks come together
    setTitleOpacity(1 - progress);
  }, []);

  useEffect(() => {
    const handleScroll = () => {
      // Cancel any pending animation frame
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
      
      // Use requestAnimationFrame for smooth updates
      rafRef.current = requestAnimationFrame(updateTransforms);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    updateTransforms();
    
    return () => {
      window.removeEventListener("scroll", handleScroll);
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [updateTransforms]);

  return (
    <section id="features" className="bg-background">
      {/* Scroll-Animated Section */}
      <div ref={sectionRef} className="relative" style={{ height: "200vh" }}>
        <div className="sticky top-0 h-screen flex items-center justify-center">
          <div className="relative w-full">
            {/* Title - positioned behind the blocks */}
            <div 
              className="absolute inset-0 flex items-center justify-center pointer-events-none z-0"
              style={{ opacity: titleOpacity }}
            >
              <h2 className="text-[10vw] font-semibold leading-[0.95] tracking-tighter text-primary md:text-[8vw] lg:text-[6vw] text-center px-6">
                Knowledge at Your Fingertips
              </h2>
            </div>

            {/* Image Grid */}
            <div className="relative z-10 grid grid-cols-1 gap-4 px-6 md:grid-cols-2 md:px-12 lg:px-20">
              {/* Left Image - comes from left */}
              <div 
                className="relative aspect-[4/3] overflow-hidden rounded-2xl"
                style={{
                  transform: `translate3d(${leftTranslateX}%, 0, 0)`,
                  WebkitTransform: `translate3d(${leftTranslateX}%, 0, 0)`,
                  backfaceVisibility: 'hidden',
                  WebkitBackfaceVisibility: 'hidden',
                }}
              >
                <Image
                  src="/images/pest-control.jpg"
                  alt="Crop health inspection"
                  fill
                  className="object-cover"
                />
                <div className="absolute bottom-6 left-6">
                  <span className="backdrop-blur-md px-4 py-2 text-sm font-medium rounded-full bg-primary/80 text-primary-foreground">
                    Pest Identification
                  </span>
                </div>
              </div>

              {/* Right Image - comes from right */}
              <div 
                className="relative aspect-[4/3] overflow-hidden rounded-2xl"
                style={{
                  transform: `translate3d(${rightTranslateX}%, 0, 0)`,
                  WebkitTransform: `translate3d(${rightTranslateX}%, 0, 0)`,
                  backfaceVisibility: 'hidden',
                  WebkitBackfaceVisibility: 'hidden',
                }}
              >
                <Image
                  src="/images/soil-health.jpg"
                  alt="Soil health analysis"
                  fill
                  className="object-cover"
                />
                <div className="absolute bottom-6 left-6">
                  <span className="backdrop-blur-md px-4 py-2 text-sm font-medium rounded-full bg-accent/80 text-accent-foreground">
                    Soil Health
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Features Grid */}
      <div className="px-6 py-20 md:px-12 md:py-28 lg:px-20 lg:py-36">
        <div className="text-center mb-16">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Comprehensive Support
          </p>
          <h3 className="mt-4 text-3xl font-semibold text-foreground md:text-4xl">
            Everything You Need to Farm Smarter
          </h3>
        </div>
        
        <div className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <div 
              key={feature.title}
              className="group p-6 rounded-2xl bg-secondary/50 hover:bg-secondary transition-colors"
            >
              <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4 group-hover:bg-primary/20 transition-colors">
                <feature.icon className="h-6 w-6 text-primary" />
              </div>
              <h4 className="text-lg font-semibold text-foreground mb-2">
                {feature.title}
              </h4>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
