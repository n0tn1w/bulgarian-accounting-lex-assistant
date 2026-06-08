import { Pipe, PipeTransform, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

// Render lightweight assistant markup safely: escape HTML first, then apply links,
// bold, code and newlines. Only http(s) links are emitted.
@Pipe({ name: 'format', standalone: true })
export class FormatPipe implements PipeTransform {
  private sanitizer = inject(DomSanitizer);

  transform(value: string | undefined | null): SafeHtml {
    if (!value) return '';
    const escaped = value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    const attrs = 'target="_blank" rel="noopener noreferrer"';
    const html = escaped
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, `<a href="$2" ${attrs}>$1</a>`)
      .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, `$1<a href="$2" ${attrs}>$2</a>`)
      .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
      .replace(/`(.+?)`/g, '<code class="mono">$1</code>')
      .replace(/\n/g, '<br>');
    return this.sanitizer.bypassSecurityTrustHtml(html);
  }
}
