-- SqlProcedure: [dbo].[getLast10Sells]

set nocount on

	select top 10 s.stockID, s.ticker, s.companyname, sd.price, ((Convert(decimal(5,2),sd.price) * 100)/sdb.price)-100 as PercentChange, ss.atwhen DateSold
	from stockbuy sb
	inner join stock s on s.stockID=sb.StockID
	inner join stocksell ss on ss.buyID=sb.buyID
	inner join stockdata sd on s.stockID=sd.stockID and sd.atwhen=ss.atwhen
	inner join stockdata sdb on s.stockID=sdb.stockID and sdb.atwhen=sb.atwhen
	where ss.atwhen < @atwhen
	and sb.channel='S'
	order by ss.atwhen desc

set nocount off
