local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.loop.fs_stat(lazypath) then
  vim.fn.system({
    "git",
    "clone",
    "--filter=tree:0",
    "https://github.com/folke/lazy.nvim.git",
    "--branch=stable", -- latest stable release
    lazypath,
  })
end
vim.opt.runtimepath:prepend(lazypath)

require("editor")

require("lazy").setup("plugins")

-- Keymaps that need to be set after plugins load (won't get overwritten)
vim.keymap.set('n', '<Leader>qq', '<Cmd>q<CR>', { desc = 'Quit all' })
vim.api.nvim_create_autocmd('User', {
  pattern = 'LazyDone',
  callback = function()
    vim.keymap.set('n', '<Leader>q', '<Cmd>q<CR>', { desc = 'Quit window' })
  end,
})

