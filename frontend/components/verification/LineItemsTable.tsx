'use client';

import { useState } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Plus, Trash2 } from 'lucide-react';

interface LineItem {
  line_no: number;
  description: string;
  quantity: number;
  unit_price: number;
}

interface LineItemsTableProps {
  items: LineItem[];
  onChange: (items: LineItem[]) => void;
}

export default function LineItemsTable({ items, onChange }: LineItemsTableProps) {
  const [editingItems, setEditingItems] = useState<LineItem[]>(items);

  const updateItem = (index: number, field: keyof LineItem, value: any) => {
    const updated = [...editingItems];
    updated[index] = { ...updated[index], [field]: value };
    setEditingItems(updated);
    onChange(updated);
  };

  const addItem = () => {
    const newItem: LineItem = {
      line_no: editingItems.length + 1,
      description: '',
      quantity: 0,
      unit_price: 0,
    };
    const updated = [...editingItems, newItem];
    setEditingItems(updated);
    onChange(updated);
  };

  const removeItem = (index: number) => {
    const updated = editingItems.filter((_, i) => i !== index);
    setEditingItems(updated);
    onChange(updated);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Line Items</h3>
        <Button onClick={addItem} size="sm" variant="outline" className="gap-2">
          <Plus className="h-4 w-4" />
          Add Item
        </Button>
      </div>
      <div className="border rounded-lg overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">#</TableHead>
              <TableHead>Description</TableHead>
              <TableHead className="w-40">Qty</TableHead>
              <TableHead className="w-32">Unit Price</TableHead>
              <TableHead className="w-32">Total</TableHead>
              <TableHead className="w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {editingItems.map((item, index) => (
              <TableRow key={index}>
                <TableCell className="font-medium">{item.line_no}</TableCell>
                <TableCell>
                  <Input
                    value={item.description}
                    onChange={(e) => updateItem(index, 'description', e.target.value)}
                    className="h-8"
                  />
                </TableCell>
                <TableCell className="w-40">
                  <Input
                    type="number"
                    value={item.quantity}
                    onChange={(e) => updateItem(index, 'quantity', parseFloat(e.target.value) || 0)}
                    className="h-8 w-full"
                  />
                </TableCell>
                <TableCell>
                  <Input
                    type="number"
                    step="0.01"
                    value={item.unit_price}
                    onChange={(e) => updateItem(index, 'unit_price', parseFloat(e.target.value) || 0)}
                    className="h-8"
                  />
                </TableCell>
                <TableCell className="font-medium">
                  ${(item.quantity * item.unit_price).toFixed(2)}
                </TableCell>
                <TableCell>
                  <Button
                    onClick={() => removeItem(index)}
                    size="sm"
                    variant="ghost"
                    className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex justify-end">
        <div className="text-sm">
          <span className="text-muted-foreground">Subtotal: </span>
          <span className="font-semibold">
            ${editingItems.reduce((sum, item) => sum + item.quantity * item.unit_price, 0).toFixed(2)}
          </span>
        </div>
      </div>
    </div>
  );
}

