"use client";

import { FadeImage } from "@/components/fade-image";
import { MessageCircle, Languages, Mic, Brain, Search, Shield } from "lucide-react";

const capabilities = [
  {
    title: "Natural Language Chat",
    description: "AI-Powered",
    image: "/images/farmer-phone.jpg",
    icon: MessageCircle,
  },
  {
    title: "Multi-Language Support",
    description: "Accessibility",
    image: "/images/farmer-community.jpg",
    icon: Languages,
  },
  {
    title: "Voice Commands",
    description: "Hands-Free",
    image: "/images/weather-farming.jpg",
    icon: Mic,
  },
  {
    title: "Smart Recommendations",
    description: "Personalized",
    image: "/images/crop-field.jpg",
    icon: Brain,
  },
  {
    title: "Knowledge Search",
    description: "RAG Technology",
    image: "/images/soil-health.jpg",
    icon: Search,
  },
  {
    title: "Verified Information",
    description: "Trusted Sources",
    image: "/images/harvest.jpg",
    icon: Shield,
  },
];

export function FeaturedProductsSection() {
  return (
    <section id="how-it-works" className="bg-background">
      {/* Section Title */}
      <div className="px-6 py-20 text-center md:px-12 md:py-28 lg:px-20 lg:py-32 lg:pb-20">
        <h2 className="text-3xl font-semibold tracking-tight text-foreground md:text-4xl lg:text-5xl">
          Powered by Advanced AI.
          <br />
          <span className="text-primary">Designed for Farmers.</span>
        </h2>
        <p className="mx-auto mt-6 max-w-lg text-muted-foreground">
          Ask questions in your language, get instant answers backed by agricultural research, government databases, and expert knowledge.
        </p>
      </div>

      {/* Capabilities Grid */}
      <div className="grid grid-cols-1 gap-4 px-6 pb-20 md:grid-cols-3 md:px-12 lg:px-20">
        {capabilities.map((item) => (
          <div key={item.title} className="group">
            {/* Image */}
            <div className="relative aspect-[4/3] overflow-hidden rounded-2xl">
              <FadeImage
                src={item.image || "/placeholder.svg"}
                alt={item.title}
                fill
                className="object-cover group-hover:scale-105"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
              <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between">
                <div className="w-10 h-10 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center">
                  <item.icon className="h-5 w-5 text-white" />
                </div>
              </div>
            </div>

            {/* Content */}
            <div className="py-6">
              <p className="mb-2 text-xs uppercase tracking-widest text-muted-foreground">
                {item.description}
              </p>
              <h3 className="text-foreground text-xl font-semibold">
                {item.title}
              </h3>
            </div>
          </div>
        ))}
      </div>

      {/* CTA Link */}
      <div className="flex justify-center px-6 pb-28 md:px-12 lg:px-20">
        
      </div>
    </section>
  );
}
