local function config_treesitter()
      require("nvim-treesitter").setup({})

      vim.api.nvim_create_autocmd("FileType", {
        callback = function(args)
          pcall(vim.treesitter.start, args.buf)
        end,
      })

      vim.o.foldmethod = "expr"
      vim.o.foldexpr = "v:lua.vim.treesitter.foldexpr()"
      vim.o.foldenable = false
end

return {
  {
    "neovim-treesitter/nvim-treesitter",
    lazy = false,
    build = ":TSUpdate",
    branch = "main",
    dependencies = {
      "neovim-treesitter/treesitter-parser-registry",
    },
    config = config_treesitter,
  },
}
