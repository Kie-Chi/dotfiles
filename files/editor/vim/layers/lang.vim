" Language and git support
Plug 'sheerun/vim-polyglot' " for multi-language highlight
let g:polyglot_disabled = ['help', 'v', 'visual-basic', 'lifelines']
Plug 'justinmk/vim-syntax-extra' " for Flex and Bison highlight
Plug 'godlygeek/tabular'
Plug 'plasticboy/vim-markdown'
let g:vim_markdown_toc_autofit = 1
let g:vim_markdown_frontmatter = 1
let g:vim_markdown_toml_frontmatter = 1
let g:vim_markdown_strikethrough = 1
autocmd FileType markdown set nofoldenable
autocmd FileType markdown let b:delimitMate_nesting_quotes = ['`']
Plug 'rust-lang/rust.vim'
autocmd FileType rust map <M-S-L> :RustFmt<CR>
Plug 'Shougo/vinarise.vim'
Plug 'kaarmu/typst.vim'
Plug 'lervag/vimtex'
autocmd FileType tex map <buffer> <LocalLeader>ll :w<CR>:VimtexCompileSS<CR>
if executable("tectonic")
    let g:vimtex_compiler_method = 'tectonic'
    let g:vimtex_compiler_tectonic = {
        \ 'options' : [
        \   '-r0',
        \   '--keep-intermediates',
        \   '--keep-logs',
        \   '--synctex'
        \ ],
        \}
end
if executable("okular")
    let g:vimtex_view_general_viewer = 'okular'
    let g:vimtex_view_general_options = '--unique file:@pdf\#src:@line@tex'
elseif executable("skimpdf")
    let g:vimtex_view_method = 'skim'
end
let g:tex_flavor = 'latex'

Plug 'github/copilot.vim'
let g:copilot_filetypes = {
            \ 'markdown': v:true,
            \ }
