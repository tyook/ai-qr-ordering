import Link from "next/link";
import {
  UtensilsCrossed,
  Store,
  Timer,
  DollarSign,
  Users,
  CreditCard,
  Globe,
  Smartphone,
  Mic,
  Zap,
  BadgePercent,
  Clock,
  Languages,
  Receipt,
  ShieldCheck,
  QrCode,
  CheckCircle,
  ArrowRight,
  ChevronDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

function FeatureItem({
  icon: Icon,
  text,
}: {
  icon: React.ComponentType<{ className?: string }>;
  text: string;
}) {
  return (
    <li className="flex items-start gap-3">
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/60 dark:bg-white/10 shadow-sm">
        <Icon className="h-4 w-4" />
      </span>
      <span className="text-sm leading-relaxed">{text}</span>
    </li>
  );
}

function StepItem({
  icon: Icon,
  title,
  description,
  step,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  step: number;
}) {
  return (
    <div className="flex flex-col items-center text-center gap-3">
      <div className="relative">
        <span className="absolute -top-2 -right-2 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
          {step}
        </span>
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-accent shadow-md">
          <Icon className="h-7 w-7 text-accent-foreground" />
        </div>
      </div>
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="text-sm text-muted-foreground max-w-[200px]">
        {description}
      </p>
    </div>
  );
}

export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      {/* ───────────────────── HERO ───────────────────── */}
      <section className="relative isolate overflow-hidden min-h-screen flex flex-col items-center justify-center px-6 text-center">
        {/* gradient background */}
        <div
          aria-hidden
          className="absolute inset-0 -z-10 bg-gradient-to-b from-amber-50 via-orange-50/60 to-background dark:from-amber-950/30 dark:via-orange-950/20 dark:to-background"
        />

        {/* glow orb */}
        <div
          aria-hidden
          className="animate-glow-pulse absolute top-1/3 left-1/2 -z-10 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-gradient-to-br from-amber-300/50 to-orange-400/40 blur-[100px] dark:from-amber-500/20 dark:to-orange-600/20"
        />

        {/* logo + name */}
        <div className="animate-fade-in-up flex items-center gap-3 mb-6">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary shadow-lg shadow-primary/25">
            <UtensilsCrossed className="h-7 w-7 text-white" />
          </div>
          <span className="text-2xl font-bold tracking-tight">QR Order</span>
        </div>

        {/* headline */}
        <h1 className="animate-fade-in-up-delay-1 max-w-3xl text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight leading-[1.1]">
          The smarter way to{" "}
          <span className="bg-gradient-to-r from-amber-600 to-orange-500 bg-clip-text text-transparent dark:from-amber-400 dark:to-orange-400">
            order
          </span>
        </h1>

        {/* subtitle */}
        <p className="animate-fade-in-up-delay-2 mt-6 max-w-xl text-lg text-muted-foreground leading-relaxed">
          AI-powered ordering that speaks every language. No lines. No waiting.
          Just scan and go.
        </p>

        {/* CTA buttons */}
        <div className="animate-fade-in-up-delay-3 mt-10 flex flex-col sm:flex-row gap-4">
          <Button
            asChild
            size="lg"
            className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg shadow-primary/25 border-0 h-12 px-8 text-base"
          >
            <Link href="/account/register">
              <Store className="mr-2 h-4 w-4" />
              I&apos;m a Restaurant Owner
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline" className="h-12 px-8 text-base">
            <Link href="/account/register">
              <Smartphone className="mr-2 h-4 w-4" />
              I&apos;m a Customer
            </Link>
          </Button>
        </div>

        {/* scroll indicator */}
        <div className="animate-float absolute bottom-8">
          <ChevronDown className="h-6 w-6 text-muted-foreground/50" />
        </div>
      </section>

      {/* ──────────── PERSONA SPLIT PANELS ──────────── */}
      <section className="relative px-6 py-24 md:py-32">
        <div className="mx-auto max-w-5xl">
          {/* section header */}
          <div className="mb-16 text-center">
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
              Built for{" "}
              <span className="bg-gradient-to-r from-amber-600 to-orange-500 bg-clip-text text-transparent dark:from-amber-400 dark:to-orange-400">
                everyone
              </span>{" "}
              at the table
            </h2>
            <p className="mt-4 text-muted-foreground max-w-lg mx-auto">
              Whether you run the restaurant or eat at one, QR Order makes the
              experience faster, easier, and more enjoyable.
            </p>
          </div>

          {/* two cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8">
            {/* OWNER CARD */}
            <Card className="relative overflow-hidden border-primary/20 bg-gradient-to-br from-accent/80 via-accent/40 to-card transition-all hover:shadow-xl hover:-translate-y-1 duration-300">
              {/* accent bar */}
              <div
                aria-hidden
                className="absolute top-0 left-0 right-0 h-1 bg-primary"
              />

              <CardHeader className="pt-8">
                {/* icon cluster */}
                <div className="flex items-center gap-2 mb-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent">
                    <Store className="h-5 w-5 text-accent-foreground" />
                  </div>
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/70">
                    <Timer className="h-4 w-4 text-accent-foreground/80" />
                  </div>
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/70">
                    <DollarSign className="h-4 w-4 text-accent-foreground/80" />
                  </div>
                </div>
                <p className="text-xs font-semibold uppercase tracking-wider text-primary">
                  For Restaurant Owners
                </p>
                <CardTitle className="text-2xl mt-1">
                  More covers. Less overhead.
                </CardTitle>
              </CardHeader>

              <CardContent>
                <ul className="space-y-4">
                  <FeatureItem
                    icon={Timer}
                    text="Faster table turns — no waiting to order or flag down the check, so guests finish sooner and the next party sits faster"
                  />
                  <FeatureItem
                    icon={Users}
                    text="Fewer servers needed — customers browse & order on their own phone"
                  />
                  <FeatureItem
                    icon={CreditCard}
                    text="Payment handled upfront — no chasing bills at the end of the meal"
                  />
                  <FeatureItem
                    icon={Globe}
                    text="Serve any customer in any language — AI translates automatically"
                  />
                </ul>
              </CardContent>

              <CardFooter>
                <Button
                  asChild
                  className="w-full bg-primary hover:bg-primary/90 text-primary-foreground border-0 shadow-md shadow-primary/20"
                >
                  <Link href="/account/register">
                    Start Free
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
              </CardFooter>
            </Card>

            {/* CUSTOMER CARD */}
            <Card className="relative overflow-hidden border-slate-200/60 dark:border-slate-700/40 bg-gradient-to-br from-slate-50/80 via-blue-50/30 to-card dark:from-slate-900/30 dark:via-blue-950/10 dark:to-card transition-all hover:shadow-xl hover:-translate-y-1 duration-300">
              {/* accent bar */}
              <div
                aria-hidden
                className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-slate-400 to-blue-500 dark:from-slate-500 dark:to-blue-400"
              />

              <CardHeader className="pt-8">
                {/* icon cluster */}
                <div className="flex items-center gap-2 mb-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-800">
                    <Smartphone className="h-5 w-5 text-slate-700 dark:text-slate-300" />
                  </div>
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100/70 dark:bg-slate-800/60">
                    <Mic className="h-4 w-4 text-slate-600 dark:text-slate-400" />
                  </div>
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100/70 dark:bg-slate-800/60">
                    <Zap className="h-4 w-4 text-slate-600 dark:text-slate-400" />
                  </div>
                </div>
                <p className="text-xs font-semibold uppercase tracking-wider text-blue-600 dark:text-blue-400">
                  For Customers
                </p>
                <CardTitle className="text-2xl mt-1">
                  Order your way.
                  <br />
                  In your language.
                </CardTitle>
              </CardHeader>

              <CardContent>
                <ul className="space-y-4">
                  <FeatureItem
                    icon={BadgePercent}
                    text="No markup, ever — you pay the same prices as the in-store menu. We don't take a cut from your order like delivery apps do"
                  />
                  <FeatureItem
                    icon={Clock}
                    text="Order before you arrive — skip the line and have food ready when you sit down"
                  />
                  <FeatureItem
                    icon={Languages}
                    text="Speak or type in any language — English, Korean, Japanese, Chinese, Spanish & more"
                  />
                  <FeatureItem
                    icon={Receipt}
                    text="Pay instantly on your phone — no waiting around for the check"
                  />
                  <FeatureItem
                    icon={ShieldCheck}
                    text="Save dietary restrictions in your profile — they're applied to every order automatically, no need to repeat yourself"
                  />
                </ul>
              </CardContent>

              <CardFooter>
                <Button
                  asChild
                  variant="outline"
                  className="w-full border-slate-300 dark:border-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <Link href="/account/register">
                    Create Account
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
              </CardFooter>
            </Card>
          </div>
        </div>
      </section>

      {/* ──────────── HOW IT WORKS ──────────── */}
      <section className="relative px-6 py-24 md:py-32 bg-muted/40">
        <div className="mx-auto max-w-4xl">
          <div className="mb-16 text-center">
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
              Three steps. That&apos;s it.
            </h2>
            <p className="mt-4 text-muted-foreground">
              From sitting down to getting your food — it&apos;s never been this
              simple.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-12 sm:gap-8">
            {/* connecting lines (desktop only) */}
            <div className="hidden sm:block absolute left-1/2 top-1/2 -translate-y-1/2 w-1/3 -translate-x-1/2">
              {/* visual connector handled by layout spacing */}
            </div>

            <StepItem
              icon={QrCode}
              title="Scan"
              description="Scan the QR code at your table or counter"
              step={1}
            />

            {/* arrow connector (desktop) */}
            <div className="hidden sm:flex absolute left-[28%] top-[52%] items-center">
              {/* handled by natural grid flow */}
            </div>

            <StepItem
              icon={Mic}
              title="Order"
              description="Speak or type your order in any language you prefer"
              step={2}
            />
            <StepItem
              icon={CheckCircle}
              title="Done"
              description="Pay on your phone and relax — food is on its way"
              step={3}
            />
          </div>

          {/* connector lines between steps (desktop) */}
          <div className="hidden sm:flex justify-center -mt-[140px] mb-[90px] px-16">
            <div className="flex items-center w-full max-w-lg">
              <div className="flex-1 border-t-2 border-dashed border-primary/30" />
              <ArrowRight className="mx-2 h-4 w-4 text-primary/50 shrink-0" />
              <div className="flex-1 border-t-2 border-dashed border-primary/30" />
              <ArrowRight className="mx-2 h-4 w-4 text-primary/50 shrink-0" />
              <div className="flex-1" />
            </div>
          </div>
        </div>
      </section>

      {/* ──────────── CLOSING CTA ──────────── */}
      <section className="relative isolate overflow-hidden px-6 py-24 md:py-32 text-center">
        {/* gradient background */}
        <div
          aria-hidden
          className="absolute inset-0 -z-10 bg-gradient-to-br from-amber-50 via-orange-50/50 to-background dark:from-amber-950/20 dark:via-orange-950/10 dark:to-background"
        />
        <div
          aria-hidden
          className="absolute -z-10 top-0 right-1/4 h-[300px] w-[300px] rounded-full bg-amber-200/30 blur-[80px] dark:bg-amber-800/10"
        />
        <div
          aria-hidden
          className="absolute -z-10 bottom-0 left-1/4 h-[250px] w-[250px] rounded-full bg-orange-200/30 blur-[80px] dark:bg-orange-800/10"
        />

        <div className="mx-auto max-w-2xl">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">
            Ready to transform your{" "}
            <span className="bg-gradient-to-r from-amber-600 to-orange-500 bg-clip-text text-transparent dark:from-amber-400 dark:to-orange-400">
              restaurant experience
            </span>
            ?
          </h2>
          <p className="mt-4 text-muted-foreground text-lg">
            Join restaurants already saving time, cutting costs, and delighting
            customers with QR Order.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              asChild
              size="lg"
              className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg shadow-primary/25 border-0 h-12 px-8 text-base"
            >
              <Link href="/account/register">
                <Store className="mr-2 h-4 w-4" />
                I&apos;m a Restaurant Owner
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="h-12 px-8 text-base">
              <Link href="/account/register">
                <Smartphone className="mr-2 h-4 w-4" />
                I&apos;m a Customer
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* ──────────── FOOTER ──────────── */}
      <footer className="border-t px-6 py-8">
        <div className="mx-auto max-w-5xl flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <UtensilsCrossed className="h-4 w-4 text-white" />
            </div>
            <span className="font-semibold">QR Order</span>
          </div>
          <p className="text-sm text-muted-foreground">
            AI-powered ordering for modern restaurants
          </p>
        </div>
      </footer>
    </div>
  );
}
