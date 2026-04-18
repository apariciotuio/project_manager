/**
 * DataTable tests — EP-12 Group 1
 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DataTable } from '@/components/layout/data-table';

type Row = { id: string; name: string; status: string };

const COLUMNS = [
  { key: 'name' as const, header: 'Name', sortable: true },
  { key: 'status' as const, header: 'Status', sortable: false },
];

const ROWS: Row[] = [
  { id: '1', name: 'Alpha', status: 'active' },
  { id: '2', name: 'Beta', status: 'inactive' },
  { id: '3', name: 'Gamma', status: 'active' },
];

describe('DataTable', () => {
  it('renders table with column headers', () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} getRowKey={(r) => r.id} />);
    expect(screen.getByRole('columnheader', { name: /name/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /status/i })).toBeInTheDocument();
  });

  it('renders all data rows', () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} getRowKey={(r) => r.id} />);
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
    expect(screen.getByText('Gamma')).toBeInTheDocument();
  });

  it('wraps table in horizontal scroll container (no overflow at page level)', () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} getRowKey={(r) => r.id} />);
    const container = screen.getByTestId('data-table-scroll-container');
    expect(container.className).toMatch(/overflow-x-auto/);
  });

  it('renders empty state when rows is empty and emptyState prop is provided', () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={[] as Row[]}
        getRowKey={(r) => r.id}
        emptyState={<div data-testid="empty">No rows</div>}
      />,
    );
    expect(screen.getByTestId('empty')).toBeInTheDocument();
  });

  it('renders loading skeleton when loading=true', () => {
    render(<DataTable columns={COLUMNS} rows={[] as Row[]} getRowKey={(r) => r.id} loading />);
    expect(screen.getByTestId('data-table-loading')).toBeInTheDocument();
  });

  it('calls onSort when sortable column header is clicked', async () => {
    const onSort = vi.fn();
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        getRowKey={(r) => r.id}
        onSort={onSort}
      />,
    );
    await userEvent.click(screen.getByRole('columnheader', { name: /name/i }));
    expect(onSort).toHaveBeenCalledWith('name', 'asc');
  });

  it('toggles sort direction on second click', async () => {
    const onSort = vi.fn();
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        getRowKey={(r) => r.id}
        onSort={onSort}
      />,
    );
    const nameHeader = screen.getByRole('columnheader', { name: /name/i });
    await userEvent.click(nameHeader);
    await userEvent.click(nameHeader);
    expect(onSort).toHaveBeenCalledWith('name', 'desc');
  });

  it('does not call onSort for non-sortable column', async () => {
    const onSort = vi.fn();
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        getRowKey={(r) => r.id}
        onSort={onSort}
      />,
    );
    await userEvent.click(screen.getByRole('columnheader', { name: /status/i }));
    expect(onSort).not.toHaveBeenCalled();
  });
});
