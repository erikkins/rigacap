-- SqlProcedure: [dbo].[getStockFromBuy]

set nocount on

select s.*, sb.AtWhen as Bought, sb.Comment as BuyComment, sb.Channel,sb.DWAPDate, ss.AtWhen as Sold, ss.Comment as SellComment,
sd.Price BuyPrice, sd2.Price SellPrice
from stock s
inner join stockbuy sb on sb.StockID = s.stockID
left join stocksell ss on ss.buyID = sb.buyID
inner join stockdata sd on sd.stockID = sb.stockID and sd.atwhen=sb.atwhen
left join stockdata sd2 on sd2.stockID = sb.stockID and sd2.atwhen=ss.atwhen
where sb.buyID = @BuyID


set nocount off
