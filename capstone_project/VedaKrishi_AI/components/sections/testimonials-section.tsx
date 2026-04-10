"use client";

import Image from "next/image";
import Link from "next/link";
import { MessageCircle, ArrowRight } from "lucide-react";

export function TestimonialsSection() {
  return (
    <section id="about" className="bg-background">
      {/* Large Text Statement */}
      <div className="px-6 py-24 md:px-12 md:py-32 lg:px-20 lg:py-40">
        <p className="mx-auto max-w-5xl text-2xl leading-relaxed text-foreground md:text-3xl lg:text-[2.5rem] lg:leading-snug">
          VedaKrishi AI brings together the wisdom of Indian agricultural traditions with cutting-edge artificial intelligence — 
          empowering every farmer with expert-level guidance, regardless of their education or resources.
        </p>
        
        {/* CTA Section */}
        <div className="mt-16 flex flex-col sm:flex-row items-center justify-center gap-6">
          <Link 
            href="/chat"
            className="inline-flex items-center gap-3 bg-primary text-primary-foreground px-8 py-4 rounded-full font-medium hover:bg-primary/90 transition-colors text-lg"
          >
            <MessageCircle className="h-6 w-6" />
            Start Your First Conversation
          </Link>
          <Link 
            href="#features"
            className="inline-flex items-center gap-2 text-primary hover:text-primary/80 transition-colors font-medium"
          >
            Learn More
            <ArrowRight className="h-5 w-5" />
          </Link>
        </div>
      </div>

      {/* About Image */}
      <div className="relative aspect-[16/9] w-full">
        <Image
          src="/images/farmer-community.jpg"
          alt="Farming community sharing knowledge"
          fill
          className="object-cover"
        />
        {/* Fade gradient overlay - background color at bottom fading to transparent at top */}
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/60 to-transparent" />
      </div>
    </section>
  );
}
