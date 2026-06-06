" Plugins that absolutely needed in most circumstance.
Plug 'raimondi/delimitmate'
let delimitMate_expand_cr = 1
au FileType verilog let b:delimitMate_quotes = "\" '"

Plug 'tpope/vim-surround'
Plug 'tpope/vim-repeat'

Plug 'tpope/vim-fugitive'

Plug 'tomtom/tcomment_vim'

Plug 'Chiel92/vim-autoformat'

Plug 'machakann/vim-highlightedyank'

" Command mode
Plug 'vim-utils/vim-husk'

if executable("fcitx") || executable("fcitx5")
    Plug 'lilydjwg/fcitx.vim'
    let g:fcitx5_remote = 'fcitx5-remote'
    if !has('gui')
        set ttimeoutlen=100
    end
elseif executable("fcitx-remote") " Probably macOS
    Plug 'CodeFalling/fcitx-vim-osx'
end

if !has('nvim-0.9')
    Plug 'editorconfig/editorconfig-vim'
end
