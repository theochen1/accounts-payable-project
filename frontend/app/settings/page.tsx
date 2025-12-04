'use client';

import Header from '@/components/layout/Header';
import GmailConnect from '@/components/settings/GmailConnect';

export default function SettingsPage() {
  return (
    <div className="flex flex-col h-full">
      <Header
        title="Settings"
        description="Configure application settings and integrations"
      />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          <GmailConnect />
        </div>
      </div>
    </div>
  );
}
