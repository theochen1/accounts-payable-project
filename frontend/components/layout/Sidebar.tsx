'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, FileText, CheckCircle2, Settings, AlertCircle, Link2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Documents', href: '/documents', icon: FileText },
  { name: 'Matched Pairs', href: '/matching/pairs', icon: Link2 },
  { name: 'Review Queue', href: '/review-queue', icon: AlertCircle },
  { name: 'Processed', href: '/processed', icon: CheckCircle2 },
];

export default function Sidebar() {
  const pathname = usePathname();

  const isItemActive = (item: any) => {
    if (item.href) {
      // For matched pairs, also check if pathname starts with /matching/pairs
      if (item.href === '/matching/pairs') {
        return pathname === item.href || pathname?.startsWith('/matching/pairs');
      }
      return pathname === item.href;
    }
    return false;
  };

  return (
    <div className="flex h-screen w-64 flex-col border-r border-border bg-background">
      <div className="flex h-16 items-center border-b border-border px-6">
        <h1 className="text-lg font-semibold text-foreground">AP Platform</h1>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4 overflow-y-auto">
        {navigation.map((item) => {
          const isActive = isItemActive(item);

          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

