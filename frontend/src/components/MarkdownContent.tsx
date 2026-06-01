import type { ReactNode } from "react";

type Block =
  | { type: "code"; language: string; content: string }
  | { type: "heading"; level: number; content: string }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "paragraph"; content: string };

export function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="space-y-3 text-sm leading-6 text-card-foreground">
      {parseBlocks(content).map((block, index) => renderBlock(block, index))}
    </div>
  );
}

function parseBlocks(content: string): Block[] {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    const fence = line.match(/^```(\w+)?\s*$/);
    if (fence) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      blocks.push({
        type: "code",
        language: fence[1] ?? "",
        content: codeLines.join("\n")
      });
      index += 1;
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      blocks.push({
        type: "heading",
        level: heading[1].length,
        content: heading[2]
      });
      index += 1;
      continue;
    }

    const unordered = line.match(/^\s*[-*]\s+(.+)$/);
    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (unordered || ordered) {
      const items: string[] = [];
      const isOrdered = Boolean(ordered);
      while (index < lines.length) {
        const match = isOrdered
          ? lines[index].match(/^\s*\d+[.)]\s+(.+)$/)
          : lines[index].match(/^\s*[-*]\s+(.+)$/);
        if (!match) {
          break;
        }
        items.push(match[1]);
        index += 1;
      }
      blocks.push({ type: "list", ordered: isOrdered, items });
      continue;
    }

    const paragraph: string[] = [line.trim()];
    index += 1;
    while (
      index < lines.length &&
      lines[index].trim() &&
      !lines[index].match(/^```|^(#{1,4})\s+|^\s*[-*]\s+|^\s*\d+[.)]\s+/)
    ) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ type: "paragraph", content: paragraph.join(" ") });
  }

  return blocks;
}

function renderBlock(block: Block, index: number) {
  if (block.type === "code") {
    return (
      <pre
        className="overflow-x-auto rounded-md border border-border bg-muted p-3 text-xs leading-5"
        key={index}
      >
        <code>{block.content}</code>
      </pre>
    );
  }

  if (block.type === "heading") {
    const className = block.level === 1 ? "text-base font-semibold" : "text-sm font-semibold";
    return (
      <div className={className} key={index}>
        {renderInline(block.content)}
      </div>
    );
  }

  if (block.type === "list") {
    const ListTag = block.ordered ? "ol" : "ul";
    return (
      <ListTag
        className={`space-y-1 pl-5 ${block.ordered ? "list-decimal" : "list-disc"}`}
        key={index}
      >
        {block.items.map((item, itemIndex) => (
          <li key={itemIndex}>{renderInline(item)}</li>
        ))}
      </ListTag>
    );
  }

  return (
    <p className="whitespace-pre-wrap" key={index}>
      {renderInline(block.content)}
    </p>
  );
}

function renderInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|\[[^\]]+\]\([^)]+\)|\*[^*]+\*|_[^_]+_)/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text))) {
    if (match.index > cursor) {
      nodes.push(text.slice(cursor, match.index));
    }

    const token = match[0];
    const key = `${match.index}-${token}`;
    if (token.startsWith("**") || token.startsWith("__")) {
      nodes.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith("`")) {
      nodes.push(
        <code className="rounded bg-muted px-1 py-0.5 text-[0.85em]" key={key}>
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith("[")) {
      const link = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      const href = link?.[2] ?? "";
      nodes.push(
        <a
          className="font-medium text-primary underline-offset-2 hover:underline"
          href={href}
          key={key}
          rel="noreferrer"
          target="_blank"
        >
          {link?.[1] ?? token}
        </a>
      );
    } else {
      nodes.push(<em key={key}>{token.slice(1, -1)}</em>);
    }
    cursor = match.index + token.length;
  }

  if (cursor < text.length) {
    nodes.push(text.slice(cursor));
  }

  return nodes;
}
