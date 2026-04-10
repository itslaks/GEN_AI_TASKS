"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Menu, X, Leaf } from "lucide-react";

export function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header 
      className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 w-[90%] max-w-3xl transition-all duration-300 ${isScrolled ? "bg-background/90 backdrop-blur-md rounded-full" : "bg-transparent"}`}
      style={{
        boxShadow: isScrolled ? "rgba(45, 90, 39, 0.08) 0px 0px 0px 1px, rgba(28, 43, 26, 0.04) 0px 1px 1px -0.5px, rgba(28, 43, 26, 0.04) 0px 3px 3px -1.5px, rgba(28, 43, 26, 0.04) 0px 6px 6px -3px" : "none"
      }}
    >
      <div className="flex items-center justify-between transition-all duration-300 px-2 pl-5 py-2">
        {/* Logo */}
        <Link href="#" className={`flex items-center gap-2 text-lg font-semibold tracking-tight transition-colors duration-300 ${isScrolled ? "text-primary" : "text-white"}`}>
          <Leaf className="h-5 w-5" />
          VedaKrishi
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden items-center gap-8 md:flex">
          <Link
            href="#features"
            className={`text-sm transition-colors ${isScrolled ? "text-muted-foreground hover:text-primary" : "text-white/70 hover:text-white"}`}
          >
            Features
          </Link>
          <Link
            href="#how-it-works"
            className={`text-sm transition-colors ${isScrolled ? "text-muted-foreground hover:text-primary" : "text-white/70 hover:text-white"}`}
          >
            How It Works
          </Link>
          <Link
            href="#benefits"
            className={`text-sm transition-colors ${isScrolled ? "text-muted-foreground hover:text-primary" : "text-white/70 hover:text-white"}`}
          >
            Benefits
          </Link>
          <Link
            href="#about"
            className={`text-sm transition-colors ${isScrolled ? "text-muted-foreground hover:text-primary" : "text-white/70 hover:text-white"}`}
          >
            About
          </Link>
        </nav>

        {/* CTA */}
        <div className="hidden items-center gap-6 md:flex">
          <Link
            href="/chat"
            className={`px-5 py-2.5 text-sm font-medium transition-all rounded-full ${isScrolled ? "bg-primary text-primary-foreground hover:bg-primary/90" : "bg-white text-primary hover:bg-white/90"}`}
          >
            Start Chatting
          </Link>
        </div>

        {/* Mobile Menu Button */}
        <button
          type="button"
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          className={`transition-colors md:hidden ${isScrolled ? "text-foreground" : "text-white"}`}
          aria-label="Toggle menu"
        >
          {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile Menu */}
      {isMenuOpen && (
        <div className="border-t border-border bg-background px-6 py-8 md:hidden rounded-b-2xl">
          <nav className="flex flex-col gap-6">
            <Link
              href="#features"
              className="text-lg text-foreground"
              onClick={() => setIsMenuOpen(false)}
            >
              Features
            </Link>
            <Link
              href="#how-it-works"
              className="text-lg text-foreground"
              onClick={() => setIsMenuOpen(false)}
            >
              How It Works
            </Link>
            <Link
              href="#benefits"
              className="text-lg text-foreground"
              onClick={() => setIsMenuOpen(false)}
            >
              Benefits
            </Link>
            <Link
              href="#about"
              className="text-lg text-foreground"
              onClick={() => setIsMenuOpen(false)}
            >
              About
            </Link>
            <Link
              href="/chat"
              className="mt-4 bg-primary px-5 py-3 text-center text-sm font-medium text-primary-foreground rounded-full"
              onClick={() => setIsMenuOpen(false)}
            >
              Start Chatting
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}
